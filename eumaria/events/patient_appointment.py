import frappe
from healthcare.healthcare.doctype.patient_appointment.patient_appointment import (
	OverlapError,
	MaximumCapacityError,
)
from frappe.utils import add_days, getdate


def mark_group_session_reminded(doc, method=None):
	"""Ensure group sessions never send reminders."""
	if getattr(doc, "is_group_session", 0):
		doc.reminded = 1


def clone_group_session_appointments():
	"""Clone group appointments four weeks ahead (runs Thursdays).

	Uses a **time-aware alive chain** detection: a source's chain is
	considered alive only if the patient has at least one appointment of
	the SAME type AND SAME time within the last 28 days.  This prevents
	an old time-slot from staying alive via clones of itself
	(self-perpetuation) once the physio deletes those clones.

	A 365‑day staleness backstop prevents any source from cloning
	indefinitely even if the physio never cleans up.
	"""
	today = getdate()
	staleness_cutoff = add_days(today, -365)

	source_appointments = frappe.get_all(
		"Patient Appointment",
		filters={
			"is_group_session": 1,
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

	created = 0
	skipped_exists = 0
	skipped_conflict = 0
	skipped_error = 0
	dead_chains = 0
	stale_sources = 0

	for source in source_appointments:
		# ── Safety backstop: source too old (>1 year) ──────────────────
		if source.appointment_date < staleness_cutoff:
			stale_sources += 1
			continue

		# ── Time-aware alive chain detection ───────────────────────────
		# The chain is alive iff the patient still has an appointment of
		# THIS type AND THIS time within the last 28 days.  Once the
		# physio deletes the old-time clones, this check fails and the
		# chain dies — it cannot self-perpetuate.
		if not frappe.db.exists(
			"Patient Appointment",
			{
				"patient": source.patient,
				"appointment_type": source.appointment_type,
				"appointment_time": source.appointment_time,
				"appointment_date": [">=", add_days(today, -28)],
				"docstatus": ["<", 2],
				"status": ["!=", "Cancelled"],
			},
		):
			dead_chains += 1
			continue

		# ── Calculate next 4 same-weekday dates from today ─────────────
		source_weekday = source.appointment_date.weekday()
		days_until = (source_weekday - today.weekday()) % 7
		if days_until == 0:
			days_until = 7  # skip today, start next week

		for i in range(4):
			target_date = add_days(today, days_until + i * 7)

			# Skip if a clone already exists for this source and target date
			if frappe.db.exists(
				"Patient Appointment",
				{
					"group_session_source": source.name,
					"appointment_date": target_date,
				},
			):
				skipped_exists += 1
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
				skipped_conflict += 1
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
				created += 1
			except (OverlapError, MaximumCapacityError):
				frappe.log_error(
					frappe.get_traceback(),
					"Group session clone skipped: validation error",
				)
				skipped_error += 1
				continue

	frappe.log_error(
		f"clone_group_session_appointments completed: "
		f"{created} created, {skipped_exists} already existed, "
		f"{skipped_conflict} patient conflicts, {skipped_error} errors, "
		f"{stale_sources} stale (>90d), {dead_chains} dead chains skipped.",
		"Group Session Clone Summary",
	)
