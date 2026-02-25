# Copyright (c) 2026, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt
from healthcare.healthcare.doctype.patient_appointment.patient_appointment import (
    invoice_appointment as original_invoice_appointment,
    cancel_appointment as original_cancel_appointment,
    check_sales_invoice_exists,
    cancel_sales_invoice,
    create_sales_invoice as original_create_sales_invoice
)


@frappe.whitelist()
def invoice_appointment(appointment_name: str, discount_percentage: float = 0, discount_amount: float = 0) -> None:
    """
    Override the invoice_appointment function to handle gift card payments.
    """
    appointment_doc = frappe.get_doc("Patient Appointment", appointment_name)
    
    # Check if gift card is being used
    if appointment_doc.use_gift_card and appointment_doc.selected_gift_card:
        # Use our gift card invoice function
        from eumaria.api.gift_card import invoice_appointment_with_gift_card
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


def create_sales_invoice(appointment_doc, discount_percentage=0, discount_amount=0):
    """
    Override create_sales_invoice to handle gift card mode of payment.
    """
    # If using gift card, get the mode_of_payment from gift card
    if appointment_doc.use_gift_card and appointment_doc.selected_gift_card:
        gift_card = frappe.get_doc("Eumaria Gift Card", appointment_doc.selected_gift_card)
        appointment_doc.mode_of_payment = gift_card.mode_of_payment
    
    # Call original function
    return original_create_sales_invoice(appointment_doc, discount_percentage, discount_amount)


def cancel_appointment(appointment_id):
    """
    Override cancel_appointment to handle gift card balance restoration.
    """
    appointment = frappe.get_doc("Patient Appointment", appointment_id)
    
    # Check if gift card was used
    if appointment.use_gift_card and appointment.selected_gift_card and appointment.gift_card_allocated_amount:
        try:
            # Restore gift card balance
            from eumaria.api.gift_card import restore_gift_card
            result = restore_gift_card(
                gift_card=appointment.selected_gift_card,
                amount=appointment.gift_card_allocated_amount
            )
            
            if result.get("success"):
                frappe.msgprint(_("Gift card balance restored: {0}").format(
                    appointment.selected_gift_card
                ), alert=True)
            else:
                frappe.msgprint(_("Warning: Could not restore gift card balance: {0}").format(
                    result.get("message")
                ), indicator="orange", alert=True)
                
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), _("Gift Card Restoration on Cancellation Error"))
            frappe.msgprint(_("Warning: Error restoring gift card balance: {0}").format(str(e)), 
                          indicator="orange", alert=True)
    
    # Call original cancel function
    original_cancel_appointment(appointment_id)


@frappe.whitelist()
def validate_gift_card_payment(appointment_name: str) -> dict:
    """
    Validate gift card payment before invoice creation.
    
    Args:
        appointment_name: Appointment name
        
    Returns:
        Dict with validation result
    """
    appointment = frappe.get_doc("Patient Appointment", appointment_name)
    
    if not appointment.use_gift_card:
        return {"valid": True, "message": _("Not using gift card")}
    
    if not appointment.selected_gift_card:
        return {"valid": False, "message": _("Gift card is selected but no gift card chosen")}
    
    if not appointment.paid_amount:
        return {"valid": False, "message": _("Paid amount is required")}
    
    # Validate gift card
    from eumaria.api.gift_card import validate_gift_card
    return validate_gift_card(
        gift_card=appointment.selected_gift_card,
        amount=appointment.paid_amount
    )


def on_sales_invoice_cancel(doc, method):
    """
    Hook for Sales Invoice cancellation to restore gift card balance.
    """
    # Check if this invoice is linked to an appointment with gift card
    for item in doc.items:
        if item.reference_dt == "Patient Appointment" and item.reference_dn:
            appointment = frappe.get_doc("Patient Appointment", item.reference_dn)
            
            if appointment.use_gift_card and appointment.selected_gift_card and appointment.gift_card_allocated_amount:
                # Restore gift card balance
                from eumaria.api.gift_card import restore_gift_card
                result = restore_gift_card(
                    gift_card=appointment.selected_gift_card,
                    amount=appointment.gift_card_allocated_amount
                )
                
                if result.get("success"):
                    # Clear gift card allocation from appointment
                    appointment.db_set({
                        "gift_card_allocated_amount": 0,
                        "selected_gift_card": "",
                        "use_gift_card": 0
                    })
                    frappe.msgprint(_("Gift card balance restored: {0}").format(
                        appointment.selected_gift_card
                    ), alert=True)
                
                break


def validate_appointment_before_save(doc, method):
    """
    Validate appointment before save to ensure gift card and regular payment are mutually exclusive.
    """
    if doc.use_gift_card and doc.mode_of_payment:
        frappe.throw(_("Cannot use both gift card and regular payment method. Please choose one."))
    
    if doc.use_gift_card and not doc.selected_gift_card:
        frappe.throw(_("Please select a gift card when using gift card payment."))
    
    if doc.use_gift_card and doc.selected_gift_card and doc.paid_amount:
        # Validate gift card balance
        from eumaria.api.gift_card import validate_gift_card
        validation = validate_gift_card(doc.selected_gift_card, doc.paid_amount, skip_balance_check=True)
        
        if not validation.get("valid"):
            frappe.throw(validation.get("message"))