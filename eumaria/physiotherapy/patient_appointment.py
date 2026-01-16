# Copyright (c) 2026, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

import datetime
import json

import frappe
from frappe import _
from frappe.core.doctype.sms_settings.sms_settings import send_sms
from frappe.utils import get_time
from healthcare.healthcare.doctype.patient_appointment.patient_appointment import send_message


def validate_patient_appointment(doc, method=None):
	"""Validate group session appointments"""
	if doc.is_group_session:
		# Require at least one attendee
		if not doc.attendees or len(doc.attendees) == 0:
			frappe.throw(_("Please add at least one attendee for group session"))
		
		# Check for duplicate patients
		patient_list = [attendee.patient for attendee in doc.attendees if attendee.patient]
		if len(patient_list) != len(set(patient_list)):
			frappe.throw(_("Duplicate patients found in attendees list. Each patient can only be added once."))
		
		# Make patient field optional for group sessions
		if not doc.patient:
			# Use first attendee as primary patient for compatibility
			doc.patient = doc.attendees[0].patient


def on_update_appointment(doc, method=None):
	"""Handle on_update events: group session titles, confirmation SMS, and reschedule SMS"""
	# Update appointment title with attendee names (for group sessions)
	if doc.is_group_session and doc.attendees:
		attendee_names = []
		for attendee in doc.attendees:
			if attendee.patient_name:
				attendee_names.append(attendee.patient_name)
		
		if attendee_names:
			# Create title with attendee names
			base_title = "Group Session"
			if doc.appointment_type:
				base_title = f"{doc.appointment_type} - Group"
			
			names_str = ", ".join(attendee_names)
			doc.title = f"{base_title}: {names_str}"
			
			# Also update the calendar event if it exists
			if hasattr(doc, 'event') and doc.event:
				try:
					event = frappe.get_doc("Event", doc.event)
					event.subject = doc.title
					event.description = f"Attendees: {names_str}"
					event.save(ignore_permissions=True)
				except Exception as e:
					frappe.log_error(f"Failed to update calendar event: {str(e)}")
	
	# Check if this is a reschedule (appointment_date or appointment_time changed)
	is_reschedule = doc.has_value_changed("appointment_date") or doc.has_value_changed("appointment_time")
	
	# Send reschedule SMS if appointment date/time changed
	if is_reschedule:
		send_reschedule_sms_on_update(doc)
	# Otherwise, send confirmation SMS to all attendees except main patient (on update, not on new insert)
	# The main patient gets confirmation SMS from Healthcare's after_insert hook
	elif not doc.is_new() and doc.is_group_session:
		message = frappe.db.get_single_value("Healthcare Settings", "appointment_confirmation_msg")
		if message:
			try:
				send_sms_to_group_attendees(doc, message, exclude_main_patient=True)
				frappe.log_error(f"Group confirmation SMS sent for appointment {doc.name}")
			except Exception:
				frappe.log_error(frappe.get_traceback(), _("Group Confirmation Message Not Sent"))


def send_sms_to_group_attendees(doc, message, exclude_main_patient=True):
	"""Send SMS to all group appointment attendees
	
	Args:
		doc: Patient Appointment document
		message: SMS message template (supports Jinja2)
		exclude_main_patient: If True, skip sending to doc.patient (main patient)
	"""
	if not doc.is_group_session or not doc.attendees:
		return
	
	# Store original patient details to restore later
	original_patient = doc.patient
	original_patient_name = doc.patient_name
	
	for attendee in doc.attendees:
		try:
			# Skip main patient if requested
			if exclude_main_patient and attendee.patient == doc.patient:
				continue
			
			# Get patient mobile number
			patient_mobile = frappe.db.get_value("Patient", attendee.patient, "mobile")
			
			if not patient_mobile:
				frappe.log_error(
					f"No mobile number found for attendee {attendee.patient_name} ({attendee.patient})",
					"Group Appointment SMS"
				)
				continue
			
			# Temporarily update doc with current attendee's details for personalized message rendering
			doc.patient = attendee.patient
			doc.patient_name = attendee.patient_name
			
			# Render message template with personalized doc context
			context = {"doc": doc, "alert": doc, "comments": None}
			if doc.get("_comments"):
				context["comments"] = json.loads(doc.get("_comments"))
			
			rendered_message = frappe.render_template(message, context)
			
			# Send SMS
			try:
				send_sms([patient_mobile], rendered_message)
				frappe.log_error(
					f"SMS sent to attendee {attendee.patient_name} ({patient_mobile})",
					"Group Appointment SMS"
				)
			except Exception as e:
				frappe.log_error(
					f"Failed to send SMS to {attendee.patient_name}: {str(e)}",
					"Group Appointment SMS"
				)
				frappe.msgprint(
					_(f"SMS failed for attendee {attendee.patient_name}. Please check SMS Settings."),
					alert=True
				)
			
		except Exception as e:
			frappe.log_error(
				f"Error processing attendee {attendee.patient}: {str(e)}",
				"Group Appointment SMS"
			)
	
	# Restore original patient details
	doc.patient = original_patient
	doc.patient_name = original_patient_name


def send_reschedule_sms_on_update(doc):
	"""Send SMS when appointment is rescheduled (appointment_date or appointment_time changed)"""
	# Only send if the appointment date or time field was actually changed
	if not (doc.has_value_changed("appointment_date") or doc.has_value_changed("appointment_time")):
		return
	
	# Send the confirmation message for the rescheduled appointment
	message = frappe.db.get_single_value("Healthcare Settings", "appointment_confirmation_msg")
	if not message:
		return
	
	try:
		if doc.is_group_session:
			# For group sessions, send to ALL attendees (including main patient)
			send_sms_to_group_attendees(doc, message, exclude_main_patient=False)
		else:
			# For single-patient appointments, use Healthcare's existing logic
			send_message(doc, message)
		
		frappe.log_error(f"Reschedule SMS sent for appointment {doc.name}")
	except Exception:
		frappe.log_error(frappe.get_traceback(), _("Appointment Reschedule Message Not Sent"))


def send_group_appointment_reminders():
	"""Send reminder SMS to all group appointment attendees (except main patient)
	
	Scheduled function to send appointment reminders to all attendees in group sessions.
	Main patient reminders are handled by Healthcare's send_appointment_reminder() function.
	"""
	if not frappe.db.get_single_value("Healthcare Settings", "send_appointment_reminder"):
		return
	
	# Get reminder timing from Healthcare Settings
	remind_before = datetime.datetime.strptime(
		frappe.db.get_single_value("Healthcare Settings", "remind_before"), "%H:%M:%S"
	)
	
	reminder_dt = datetime.datetime.now() + datetime.timedelta(
		hours=remind_before.hour, 
		minutes=remind_before.minute, 
		seconds=remind_before.second
	)
	
	# Query group appointments within reminder window that haven't been reminded
	group_appointments = frappe.db.get_all(
		"Patient Appointment",
		filters={
			"is_group_session": 1,
			"appointment_datetime": ["between", (datetime.datetime.now(), reminder_dt)],
			"reminded": 0,
			"status": ["!=", "Cancelled"],
		},
	)
	
	message = frappe.db.get_single_value("Healthcare Settings", "appointment_reminder_msg")
	if not message:
		return
	
	for appointment in group_appointments:
		try:
			doc = frappe.get_doc("Patient Appointment", appointment.name)
			
			# Send reminder to all attendees except main patient
			send_sms_to_group_attendees(doc, message, exclude_main_patient=True)
			
			# Mark as reminded to prevent duplicate sends
			frappe.db.set_value("Patient Appointment", doc.name, "reminded", 1)
			
			frappe.log_error(
				f"Group appointment reminders sent for {doc.name}",
				"Group Appointment Reminders"
			)
			
		except Exception as e:
			frappe.log_error(
				f"Failed to send reminders for {appointment.name}: {str(e)}",
				"Group Appointment Reminders"
			)

