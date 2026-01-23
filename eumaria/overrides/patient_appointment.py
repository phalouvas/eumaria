import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime
from healthcare.healthcare.doctype.patient_appointment import patient_appointment as core_patient_appointment


class PatientAppointment(core_patient_appointment.PatientAppointment):
	"""Custom Patient Appointment with group session SMS suppression."""

	def validate(self):
		super().validate()
		if getattr(self, "is_group_session", 0):
			self.reminded = 1

	def after_insert(self):
		self.update_prescription_details()
		self.set_payment_details()

		if not getattr(self, "is_group_session", 0):
			core_patient_appointment.send_confirmation_msg(self)

		self.insert_calendar_event()

		if self.service_request:
			frappe.db.set_value(
				"Service Request", self.service_request, "status", "completed-Request Status"
			)


@frappe.whitelist()
def send_appointment_sms(appointment_name: str) -> None:
	"""Send confirmation SMS manually for a future appointment.

	Respects Healthcare Settings toggle for confirmation messages and uses the
	configured confirmation template. Marks the appointment as reminded to
	avoid duplicate sends.
	"""

	appointment = frappe.get_doc("Patient Appointment", appointment_name)

	if not appointment.appointment_date:
		raise frappe.ValidationError(_("Appointment date is required to send SMS."))

	if not frappe.db.get_single_value("Healthcare Settings", "send_appointment_confirmation"):
		raise frappe.ValidationError(
			_("Appointment confirmation SMS is disabled in Healthcare Settings.")
		)

	appointment_datetime = get_datetime(
		f"{appointment.appointment_date} {appointment.appointment_time or '00:00:00'}"
	)
	if appointment_datetime <= now_datetime():
		raise frappe.ValidationError(_("SMS can only be sent for future appointments."))

	patient_mobile = frappe.db.get_value("Patient", appointment.patient, "mobile")
	if not patient_mobile:
		raise frappe.ValidationError(_("Patient does not have a mobile number set."))

	message = frappe.db.get_single_value("Healthcare Settings", "appointment_confirmation_msg")
	if not message:
		raise frappe.ValidationError(_("Appointment Confirmation Message is empty in Healthcare Settings."))

	try:
		core_patient_appointment.send_message(appointment, message)
	except Exception:
		frappe.log_error(frappe.get_traceback(), _("Appointment SMS Not Sent"))
		frappe.throw(_("Appointment SMS could not be sent. Please check SMS Settings."))

	appointment.db_set("reminded", 1)
	appointment.add_comment("Info", _("Manual SMS sent to {0}.").format(patient_mobile))
	frappe.msgprint(_("SMS sent to {0}.").format(patient_mobile), alert=True)
