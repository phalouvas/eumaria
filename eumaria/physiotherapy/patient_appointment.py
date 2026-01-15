# Copyright (c) 2026, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

import frappe
from frappe import _


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


def on_update_patient_appointment(doc, method=None):
	"""Update appointment title with attendee names"""
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
