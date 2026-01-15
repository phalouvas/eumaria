# Copyright (c) 2026, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	"""Create custom fields for Patient Appointment to support group sessions"""
	
	custom_fields = {
		"Patient Appointment": [
			{
				"fieldname": "is_group_session",
				"label": "Is Group Session",
				"fieldtype": "Check",
				"insert_after": "appointment_type",
				"default": "0",
				"description": "Check this to enable group session with multiple attendees"
			},
			{
				"fieldname": "attendees",
				"label": "Attendees",
				"fieldtype": "Table",
				"options": "Group Appointment Attendee",
				"insert_after": "is_group_session",
				"depends_on": "eval:doc.is_group_session==1",
				"description": "List of patients attending this group session"
			}
		]
	}
	
	create_custom_fields(custom_fields, update=True)
