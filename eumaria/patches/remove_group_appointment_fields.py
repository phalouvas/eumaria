# Copyright (c) 2026, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Remove custom fields for group appointment functionality"""
	
	# Remove the custom fields that were created for group sessions
	custom_fields_to_remove = [
		("Patient Appointment", "is_group_session"),
		("Patient Appointment", "attendees"),
	]
	
	for doctype, fieldname in custom_fields_to_remove:
		try:
			# Check if the custom field exists
			if frappe.db.exists("Custom Field", {
				"dt": doctype,
				"fieldname": fieldname
			}):
				# Delete the custom field
				frappe.db.delete("Custom Field", {
					"dt": doctype,
					"fieldname": fieldname
				})
				frappe.db.commit()
				frappe.logger().info(f"Removed custom field {fieldname} from {doctype}")
		except Exception as e:
			frappe.logger().error(f"Error removing custom field {fieldname} from {doctype}: {str(e)}")
