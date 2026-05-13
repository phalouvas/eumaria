import datetime
import frappe
from frappe import _
from frappe.utils import flt, get_datetime, get_time, getdate, now_datetime
from healthcare.healthcare.doctype.patient_appointment import patient_appointment as core_patient_appointment
from healthcare.healthcare.doctype.patient_appointment.patient_appointment import (
	OverlapError,
	MaximumCapacityError
)


class PatientAppointment(core_patient_appointment.PatientAppointment):
	"""Custom Patient Appointment with group session SMS suppression and practitioner overlap allowed."""

	def validate(self):
		super().validate()
		if getattr(self, "is_group_session", 0):
			self.reminded = 1

	def validate_overlaps(self):
		"""
		Override to allow practitioner to have multiple concurrent appointments.
		Only prevent same patient from having overlapping appointments.
		"""
		if self.appointment_based_on_check_in:
			if frappe.db.exists({
				"doctype": "Patient Appointment",
				"patient": self.patient,
				"appointment_date": self.appointment_date,
				"appointment_time": self.appointment_time,
				"appointment_based_on_check_in": True,
				"name": ["!=", self.name],
			}):
				frappe.throw(_("Patient already has an appointment booked for the same day!"), OverlapError)
			return

		if not self.patient:
			return

		end_time = datetime.datetime.combine(
			getdate(self.appointment_date), get_time(self.appointment_time)
		) + datetime.timedelta(minutes=flt(self.duration))

		# Only check for PATIENT overlaps, not practitioner
		overlapping_appointments = frappe.db.sql(
			"""
			SELECT
				name, practitioner, patient, appointment_time, duration, service_unit
			FROM
				`tabPatient Appointment`
			WHERE
				appointment_date=%(appointment_date)s AND name!=%(name)s 
				AND status NOT IN ("Closed", "Cancelled") AND
				patient=%(patient)s AND
				((appointment_time<%(appointment_time)s AND appointment_time + INTERVAL duration MINUTE>%(appointment_time)s) OR
				(appointment_time>%(appointment_time)s AND appointment_time<%(end_time)s) OR
				(appointment_time=%(appointment_time)s))
			""",
			{
				"appointment_date": self.appointment_date,
				"name": self.name,
				"patient": self.patient,
				"appointment_time": self.appointment_time,
				"end_time": end_time.time(),
			},
			as_dict=True,
		)

		if overlapping_appointments:
			frappe.throw(
				_("Patient already has appointment {} at this time").format(
					frappe.bold(", ".join([apt["name"] for apt in overlapping_appointments]))
				),
				OverlapError,
			)

		# Still validate service unit capacity if applicable
		if self.service_unit:
			allow_overlap, service_unit_capacity = frappe.get_value(
				"Healthcare Service Unit", 
				self.service_unit, 
				["overlap_appointments", "service_unit_capacity"]
			)
			if allow_overlap and service_unit_capacity:
				# Count appointments at this service unit during this time
				su_appointments = frappe.db.sql(
					"""
					SELECT COUNT(*) as count
					FROM `tabPatient Appointment`
					WHERE
						appointment_date=%(appointment_date)s AND name!=%(name)s
						AND status NOT IN ("Closed", "Cancelled")
						AND service_unit=%(service_unit)s AND
						((appointment_time<%(appointment_time)s AND appointment_time + INTERVAL duration MINUTE>%(appointment_time)s) OR
						(appointment_time>%(appointment_time)s AND appointment_time<%(end_time)s) OR
						(appointment_time=%(appointment_time)s))
					""",
					{
						"appointment_date": self.appointment_date,
						"name": self.name,
						"service_unit": self.service_unit,
						"appointment_time": self.appointment_time,
						"end_time": end_time.time(),
					},
					as_dict=True,
				)
				
				count = su_appointments[0].count if su_appointments else 0
				if count >= service_unit_capacity:
					frappe.throw(
						_("Not allowed, {} cannot exceed maximum capacity {}").format(
							frappe.bold(self.service_unit), 
							frappe.bold(service_unit_capacity)
						),
						MaximumCapacityError,
					)

	def on_update(self):
		"""Override to reset reminded flag when appointment is rescheduled."""
		super().on_update()

		if not getattr(self, "is_group_session", 0):
			doc_before = self.get_doc_before_save()
			if doc_before:
				old_dt = get_datetime(
					f"{doc_before.appointment_date} {doc_before.appointment_time or '00:00:00'}"
				)
				new_dt = get_datetime(
					f"{self.appointment_date} {self.appointment_time or '00:00:00'}"
				)
				if old_dt != new_dt:
					frappe.db.set_value("Patient Appointment", self.name, "reminded", 0)
					self.reminded = 0

	def after_insert(self):
		self.update_prescription_details()
		self.set_payment_details()

		# ── Disabled: automatic confirmation SMS on new appointment ──────────────
		# Disabled May 2026 per customer request — appointments should only
		# receive the day-before reminder, not an immediate confirmation SMS.
		#
		# The manual "Send Confirmation SMS" button on the form still works
		# (see send_appointment_sms whitelisted method below).
		# The scheduled day-before reminder is also unaffected.
		#
		# To re-enable: uncomment the block below.
		# ──────────────────────────────────────────────────────────────────────────
		# if not getattr(self, "is_group_session", 0):
		# 	self.reminded = 0
		# 	message = frappe.db.get_single_value("Healthcare Settings", "appointment_confirmation_msg")
		# 	if not message:
		# 		message = _("Your appointment is scheduled for {0}.").format(
		# 			_get_appointment_datetime_for_sms(self)
		# 		)
		# 	_send_templated_sms(self, message, "Appointment SMS Not Sent")

		self.insert_calendar_event()

		if self.service_request:
			frappe.db.set_value(
				"Service Request", self.service_request, "status", "completed-Request Status"
			)


def _add_sms_activity(appointment_name: str, content: str) -> None:
	"""Write an explicit timeline comment entry for SMS actions."""
	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "Patient Appointment",
			"reference_name": appointment_name,
			"content": content,
		}
	).insert(ignore_permissions=True)


def _get_appointment_datetime_for_sms(appointment) -> str:
	"""Return appointment datetime formatted for SMS templates with weekday."""
	appointment_datetime = get_datetime(
		f"{appointment.appointment_date} {appointment.appointment_time or '00:00:00'}"
	)

	weekday_names_en = [
		"Monday",
		"Tuesday",
		"Wednesday",
		"Thursday",
		"Friday",
		"Saturday",
		"Sunday",
	]
	weekday_names_el = [
		"Δευτέρα",
		"Τρίτη",
		"Τετάρτη",
		"Πέμπτη",
		"Παρασκευή",
		"Σάββατο",
		"Κυριακή",
	]

	active_lang = (getattr(frappe.local, "lang", "") or "").lower()
	weekday_names = weekday_names_el if active_lang.startswith("el") else weekday_names_en
	weekday_name = weekday_names[appointment_datetime.weekday()]

	return f"{weekday_name} {appointment_datetime.strftime('%d-%b-%Y %H:%M')}"


def _render_sms_template(template: str, appointment) -> str:
	"""Render a message template with custom appointment datetime formatting."""
	doc_context = appointment.as_dict()
	doc_context["appointment_datetime"] = _get_appointment_datetime_for_sms(appointment)
	return frappe.render_template(template, {"doc": doc_context})


def _send_templated_sms(appointment, template: str, error_title: str) -> None:
	"""Render a template and send SMS using Healthcare's sender utility."""
	rendered_message = _render_sms_template(template, appointment)
	try:
		core_patient_appointment.send_message(appointment, rendered_message)
	except Exception:
		frappe.log_error(frappe.get_traceback(), _(error_title))
		frappe.throw(_("Appointment SMS could not be sent. Please check SMS Settings."))


@frappe.whitelist()
def send_appointment_sms(appointment_name: str) -> None:
	"""Send confirmation SMS manually for a future appointment.

	This is a manual action, so it works independently of Healthcare Settings.
	Uses the configured confirmation template if available, otherwise sends a default message.
	Marks the appointment as reminded to avoid duplicate sends.
	"""

	appointment = frappe.get_doc("Patient Appointment", appointment_name)

	if not appointment.appointment_date:
		raise frappe.ValidationError(_("Appointment date is required to send SMS."))

	appointment_datetime = get_datetime(
		f"{appointment.appointment_date} {appointment.appointment_time or '00:00:00'}"
	)
	if appointment_datetime <= now_datetime():
		raise frappe.ValidationError(_("SMS can only be sent for future appointments."))

	patient_mobile = frappe.db.get_value("Patient", appointment.patient, "mobile")
	if not patient_mobile:
		raise frappe.ValidationError(_("Patient does not have a mobile number set."))

	# Use configured message if available, otherwise use default
	message = frappe.db.get_single_value("Healthcare Settings", "appointment_confirmation_msg")
	if not message:
		message = _("Your appointment is scheduled for {0}.").format(
			_get_appointment_datetime_for_sms(appointment)
		)

	_send_templated_sms(appointment, message, "Appointment SMS Not Sent")

	appointment.db_set("reminded", 1)
	_add_sms_activity(appointment.name, _("Manual SMS sent to {0}.").format(patient_mobile))
	frappe.msgprint(_("SMS sent to {0}.").format(patient_mobile), alert=True)


@frappe.whitelist()
def send_custom_appointment_sms(appointment_name: str, message: str) -> None:
	"""Send a user-composed SMS manually for a future appointment."""

	appointment = frappe.get_doc("Patient Appointment", appointment_name)

	if not appointment.appointment_date:
		raise frappe.ValidationError(_("Appointment date is required to send SMS."))

	appointment_datetime = get_datetime(
		f"{appointment.appointment_date} {appointment.appointment_time or '00:00:00'}"
	)
	if appointment_datetime <= now_datetime():
		raise frappe.ValidationError(_("SMS can only be sent for future appointments."))

	patient_mobile = frappe.db.get_value("Patient", appointment.patient, "mobile")
	if not patient_mobile:
		raise frappe.ValidationError(_("Patient does not have a mobile number set."))

	if not message or not str(message).strip():
		raise frappe.ValidationError(_("Message is required."))

	try:
		core_patient_appointment.send_message(appointment, str(message).strip())
	except Exception:
		frappe.log_error(frappe.get_traceback(), _("Custom Appointment SMS Not Sent"))
		frappe.throw(_("Appointment SMS could not be sent. Please check SMS Settings."))

	_add_sms_activity(appointment.name, _("Custom SMS sent to {0}.").format(patient_mobile))
	frappe.msgprint(_("SMS sent to {0}.").format(patient_mobile), alert=True)
