# Copyright (c) 2026, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


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

	set_default_patient_appointment_view()


def set_default_patient_appointment_view():
	"""Force Patient Appointment to open in Calendar view by default."""
	existing = frappe.db.exists(
		"Property Setter",
		{
			"doc_type": "Patient Appointment",
			"property": "default_view",
		},
	)

	if existing:
		current_value = frappe.db.get_value("Property Setter", existing, "value")
		if current_value != "Calendar":
			frappe.db.set_value("Property Setter", existing, "value", "Calendar")
		return

	make_property_setter(
		"Patient Appointment",
		None,
		"default_view",
		"Calendar",
		"Select",
		for_doctype=True,
	)
