# Copyright (c) 2026, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from healthcare.healthcare.doctype.patient_appointment.patient_appointment import (
    invoice_appointment as original_invoice_appointment,
    cancel_appointment as original_cancel_appointment,
)


@frappe.whitelist()
def invoice_appointment(appointment_name: str, discount_percentage: float = 0, discount_amount: float = 0) -> None:
    """
    Override the invoice_appointment function to handle gift card payments.
    """
    appointment_doc = frappe.get_doc("Patient Appointment", appointment_name)

    # Check if gift card is being used
    if appointment_doc.use_gift_card and appointment_doc.selected_gift_card:
        from eumaria.api.gift_card import invoice_appointment_with_gift_card

        if appointment_doc.mode_of_payment:
            frappe.throw(_("Cannot use both gift card and regular payment method. Please choose one."))

        result = invoice_appointment_with_gift_card(
            appointment_name=appointment_name,
            discount_percentage=discount_percentage,
            discount_amount=discount_amount,
            gift_card=appointment_doc.selected_gift_card
        )
        
        if not result.get("success"):
            frappe.throw(result.get("message"))
        
        return
    
    # Otherwise, use the original function
    original_invoice_appointment(appointment_name, discount_percentage, discount_amount)


def cancel_appointment(appointment_id):
    """Keep healthcare cancellation flow; gift-card balance sync is handled on Sales Invoice cancel hook."""
    original_cancel_appointment(appointment_id)


def on_sales_invoice_cancel(doc, method):
    """Sync gift-card availability from its linked advance and clear appointment allocation metadata."""
    # Check if this invoice is linked to an appointment with gift card
    for item in doc.items:
        if item.reference_dt == "Patient Appointment" and item.reference_dn:
            appointment = frappe.get_doc("Patient Appointment", item.reference_dn)

            if appointment.use_gift_card and appointment.selected_gift_card:
                from eumaria.api.gift_card import sync_gift_card_remaining_amount

                sync_gift_card_remaining_amount(appointment.selected_gift_card)
                appointment.db_set(
                    {
                        "gift_card_allocated_amount": 0,
                        "selected_gift_card": "",
                        "use_gift_card": 0,
                    }
                )

            break