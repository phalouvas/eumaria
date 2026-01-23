import frappe
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
