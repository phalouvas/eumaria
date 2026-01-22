# Copyright (c) 2026, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Delete Group Appointment Attendee doctype"""
	
	try:
		# Check if the doctype exists
		if frappe.db.exists("DocType", "Group Appointment Attendee"):
			# Delete the doctype
			frappe.delete_doc("DocType", "Group Appointment Attendee", force=True)
			frappe.db.commit()
			frappe.logger().info("Deleted Group Appointment Attendee doctype")
	except Exception as e:
		frappe.logger().error(f"Error deleting Group Appointment Attendee doctype: {str(e)}")
