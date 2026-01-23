# Copyright (c) 2026, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	"""Create custom fields used by Eumaria customizations."""

	custom_fields = {
		"Patient Appointment": [
			{
				"fieldname": "is_group_session",
				"label": "Is Group Session",
				"fieldtype": "Check",
				"insert_after": "appointment_type",
			},
			{
				"fieldname": "group_session_source",
				"label": "Group Session Source",
				"fieldtype": "Link",
				"options": "Patient Appointment",
				"read_only": 1,
				"hidden": 1,
				"no_copy": 1,
				"insert_after": "is_group_session",
			},
		],
	}

	create_custom_fields(custom_fields, update=True)
