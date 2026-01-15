# Copyright (c) 2026, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import nowdate


@frappe.whitelist()
def create_group_invoices(appointment_name):
	"""
	Create Sales Invoices for all attendees in a group session
	
	Args:
		appointment_name: Name of the Patient Appointment
		
	Returns:
		List of created invoice names
	"""
	appointment = frappe.get_doc("Patient Appointment", appointment_name)
	
	if not appointment.is_group_session:
		frappe.throw(_("This is not a group session appointment"))
	
	if not appointment.attendees:
		frappe.throw(_("No attendees found in this group session"))
	
	# Check if already invoiced
	if appointment.invoiced:
		frappe.throw(_("Invoices already created for this appointment"))
	
	created_invoices = []
	
	for attendee in appointment.attendees:
		try:
			# Get patient info
			patient = frappe.get_doc("Patient", attendee.patient)
			
			# Create Sales Invoice
			invoice = frappe.new_doc("Sales Invoice")
			invoice.patient = attendee.patient
			invoice.patient_name = attendee.patient_name
			invoice.customer = patient.customer
			invoice.posting_date = nowdate()
			invoice.due_date = nowdate()
			invoice.company = appointment.company
			
			# Add appointment reference if available
			if hasattr(invoice, 'ref_patient_appointment'):
				invoice.ref_patient_appointment = appointment_name
			
			# Get billing item from appointment
			billing_item = appointment.billing_item or get_healthcare_service_item()
			
			if not billing_item:
				frappe.msgprint(_("No billing item found. Please set Healthcare Service Item in Healthcare Settings or appointment."))
				continue
			
			# Add invoice item
			invoice.append("items", {
				"item_code": billing_item,
				"item_name": f"{appointment.appointment_type or 'Group Session'} - {appointment.appointment_date}",
				"qty": 1,
				"uom": "Nos",
				"description": f"Group Session Attendance - {appointment.appointment_date}",
			})
			
			# Save invoice (user will set price and submit manually)
			invoice.insert(ignore_permissions=False)
			created_invoices.append(invoice.name)
			
		except Exception as e:
			frappe.log_error(f"Failed to create invoice for {attendee.patient}: {str(e)}")
			frappe.msgprint(_("Failed to create invoice for {0}: {1}").format(attendee.patient_name, str(e)))
	
	if created_invoices:
		# Mark appointment as invoiced
		appointment.invoiced = 1
		appointment.save(ignore_permissions=True)
		
		frappe.msgprint(
			_("Created {0} invoice(s) successfully").format(len(created_invoices)),
			alert=True
		)
	
	return created_invoices


def get_healthcare_service_item():
	"""Get the default healthcare service item from settings"""
	return frappe.db.get_single_value("Healthcare Settings", "inpatient_visit_charge_item")
