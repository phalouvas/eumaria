import datetime

import frappe
from healthcare.healthcare.doctype.patient_appointment.patient_appointment import (
	OverlapError,
	MaximumCapacityError,
)
from frappe.utils import add_days, getdate, get_datetime, get_time, flt


def mark_group_session_reminded(doc, method=None):
	"""Ensure group sessions never send reminders."""
	if getattr(doc, "is_group_session", 0):
		doc.reminded = 1


def clone_group_session_appointments():
	"""Clone current week's group appointments four weeks ahead (runs Thursdays)."""
	# Identify week boundaries (Mon–Sun)
	today = getdate()
	start_current_week = today - datetime.timedelta(days=today.weekday())
	end_current_week = start_current_week + datetime.timedelta(days=6)

	source_appointments = frappe.get_all(
		"Patient Appointment",
		filters={
			"is_group_session": 1,
			"appointment_date": ["between", (start_current_week, end_current_week)],
			"status": ["!=", "Cancelled"],
			"docstatus": ["<", 2],
			"group_session_source": ["is", "not set"],
		},
		fields=[
			"name",
			"patient",
			"appointment_type",
			"company",
			"practitioner",
			"department",
			"service_unit",
			"appointment_date",
			"appointment_time",
			"duration",
			"notes",
			"referring_practitioner",
			"therapy_plan",
			"therapy_type",
			"procedure_template",
			"add_video_conferencing",
		],
	)

	for source in source_appointments:
		for week_offset in (7, 14, 21, 28):
			target_date = add_days(source.appointment_date, week_offset)

			# Skip if a clone already exists for this source and target date
			if frappe.db.exists(
				"Patient Appointment",
				{
					"group_session_source": source.name,
					"appointment_date": target_date,
				},
			):
				continue

			# Pre-insert safety check: skip if patient already has an
			# appointment at this target date and time
			if frappe.db.exists(
				"Patient Appointment",
				{
					"patient": source.patient,
					"appointment_date": target_date,
					"appointment_time": source.appointment_time,
					"status": ["not in", ("Cancelled", "Closed")],
				},
			):
				frappe.log_error(
					{
						"source_appointment": source.name,
						"target_date": target_date,
						"patient": source.patient,
					},
					"Group session clone skipped: patient already booked",
				)
				continue

			clone = frappe.new_doc("Patient Appointment")
			clone.update(
				{
					"patient": source.patient,
					"appointment_type": source.appointment_type,
					"company": source.company,
					"practitioner": source.practitioner,
					"department": source.department,
					"service_unit": source.service_unit,
					"appointment_date": target_date,
					"appointment_time": source.appointment_time,
					"duration": source.duration,
					"notes": source.notes,
					"referring_practitioner": source.referring_practitioner,
					"therapy_plan": source.therapy_plan,
					"therapy_type": source.therapy_type,
					"procedure_template": source.procedure_template,
					"add_video_conferencing": source.add_video_conferencing,
					"is_group_session": 1,
					"group_session_source": source.name,
				}
			)
			try:
				clone.insert(ignore_permissions=True)
			except (OverlapError, MaximumCapacityError):
				frappe.log_error(
					frappe.get_traceback(),
					"Group session clone skipped: validation error",
				)
				continue
