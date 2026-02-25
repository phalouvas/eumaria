# Copyright (c) 2026, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate
from frappe.model.document import Document


@frappe.whitelist()
def get_gift_cards_for_customer(customer: str) -> list:
    """
    Get active gift cards for a specific customer.
    
    Args:
        customer: Customer name/link
        
    Returns:
        List of gift card documents with name, remaining_amount, ends_on
    """
    if not customer:
        return []
    
    today = getdate(nowdate())
    
    gift_cards = frappe.get_all(
        "Eumaria Gift Card",
        filters={
            "customer": customer,
            "disabled": 0,
            "docstatus": 1,  # Submitted documents only
            "ends_on": [">=", today],
            "starts_on": ["<=", today],
        },
        fields=["name", "remaining_amount", "ends_on", "initial_amount", "mode_of_payment"],
        order_by="ends_on asc"
    )
    
    # Format for display
    for card in gift_cards:
        card["display"] = f"{card['name']} (Balance: {card['remaining_amount']}, Valid until: {card['ends_on']})"
    
    return gift_cards


@frappe.whitelist()
def validate_gift_card(gift_card: str, amount: float) -> dict:
    """
    Validate if a gift card can be used for a payment.
    
    Args:
        gift_card: Gift card name
        amount: Amount to pay
        
    Returns:
        Dict with validation result and message
    """
    if not gift_card:
        return {"valid": False, "message": _("Gift card is required")}
    
    try:
        amount = flt(amount)
        doc = frappe.get_doc("Eumaria Gift Card", gift_card)
        
        # Check if gift card exists and is valid
        if doc.disabled:
            return {"valid": False, "message": _("Gift card is disabled")}
        
        if doc.docstatus != 1:
            return {"valid": False, "message": _("Gift card is not submitted")}
        
        today = getdate(nowdate())
        if doc.ends_on and getdate(doc.ends_on) < today:
            return {"valid": False, "message": _("Gift card has expired")}
        
        if doc.starts_on and getdate(doc.starts_on) > today:
            return {"valid": False, "message": _("Gift card is not yet valid")}
        
        # Check balance
        if flt(doc.remaining_amount) < amount:
            return {
                "valid": False, 
                "message": _("Insufficient balance. Available: {0}, Required: {1}").format(
                    doc.remaining_amount, amount
                )
            }
        
        return {
            "valid": True,
            "message": _("Gift card validated successfully"),
            "remaining_amount": doc.remaining_amount,
            "mode_of_payment": doc.mode_of_payment
        }
        
    except frappe.DoesNotExistError:
        return {"valid": False, "message": _("Gift card not found")}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _("Gift Card Validation Error"))
        return {"valid": False, "message": _("Error validating gift card: {0}").format(str(e))}


@frappe.whitelist()
def allocate_gift_card(gift_card: str, amount: float, sales_invoice: str = None, appointment: str = None) -> dict:
    """
    Allocate gift card balance to a payment.
    
    Args:
        gift_card: Gift card name
        amount: Amount to allocate
        sales_invoice: Related sales invoice (optional)
        appointment: Related appointment (optional)
        
    Returns:
        Dict with allocation result
    """
    try:
        amount = flt(amount)
        doc = frappe.get_doc("Eumaria Gift Card", gift_card)
        
        # Validate before allocation
        validation = validate_gift_card(gift_card, amount)
        if not validation.get("valid"):
            return validation
        
        # Create payment entry
        payment_entry = create_gift_card_payment_entry(doc, amount, sales_invoice, appointment)
        
        # Update gift card balance
        new_balance = flt(doc.remaining_amount) - amount
        doc.db_set("remaining_amount", new_balance)
        
        # Link payment entry to gift card
        doc.db_set("payment_entry", payment_entry.name)
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": _("Gift card allocated successfully"),
            "payment_entry": payment_entry.name,
            "new_balance": new_balance
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), _("Gift Card Allocation Error"))
        return {
            "success": False,
            "message": _("Error allocating gift card: {0}").format(str(e))
        }


def create_gift_card_payment_entry(gift_card_doc: Document, amount: float, sales_invoice: str = None, appointment: str = None) -> Document:
    """
    Create a payment entry for gift card allocation.
    
    Args:
        gift_card_doc: Gift card document
        amount: Amount to allocate
        sales_invoice: Related sales invoice
        appointment: Related appointment
        
    Returns:
        Payment Entry document
    """
    # Get customer and company from gift card
    customer = gift_card_doc.customer
    company = frappe.defaults.get_user_default("company") or frappe.db.get_single_value("Global Defaults", "default_company")
    
    # Create payment entry
    payment_entry = frappe.get_doc({
        "doctype": "Payment Entry",
        "payment_type": "Receive",
        "mode_of_payment": gift_card_doc.mode_of_payment,
        "party_type": "Customer",
        "party": customer,
        "paid_amount": amount,
        "received_amount": amount,
        "company": company,
        "reference_date": nowdate(),
        "reference_no": gift_card_doc.name,
        "remarks": _("Gift card payment for {0}").format(
            f"Sales Invoice {sales_invoice}" if sales_invoice else f"Appointment {appointment}"
        )
    })
    
    # Insert and submit
    payment_entry.insert(ignore_permissions=True)
    payment_entry.submit()
    
    # Link to sales invoice if provided
    if sales_invoice:
        frappe.get_doc({
            "doctype": "Payment Entry Reference",
            "parent": payment_entry.name,
            "parenttype": "Payment Entry",
            "parentfield": "references",
            "reference_doctype": "Sales Invoice",
            "reference_name": sales_invoice,
            "allocated_amount": amount
        }).insert(ignore_permissions=True)
    
    return payment_entry


@frappe.whitelist()
def restore_gift_card(gift_card: str, amount: float) -> dict:
    """
    Restore gift card balance (e.g., when invoice is cancelled).
    
    Args:
        gift_card: Gift card name
        amount: Amount to restore
        
    Returns:
        Dict with restoration result
    """
    try:
        amount = flt(amount)
        doc = frappe.get_doc("Eumaria Gift Card", gift_card)
        
        # Update gift card balance
        new_balance = flt(doc.remaining_amount) + amount
        doc.db_set("remaining_amount", new_balance)
        
        # Cancel payment entry if exists
        if doc.payment_entry:
            payment_entry = frappe.get_doc("Payment Entry", doc.payment_entry)
            if payment_entry.docstatus == 1:
                payment_entry.cancel()
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": _("Gift card balance restored successfully"),
            "new_balance": new_balance
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), _("Gift Card Restoration Error"))
        return {
            "success": False,
            "message": _("Error restoring gift card: {0}").format(str(e))
        }


@frappe.whitelist()
def invoice_appointment_with_gift_card(appointment_name: str, discount_percentage: float = 0, discount_amount: float = 0, gift_card: str = None) -> dict:
    """
    Create invoice for appointment with gift card payment.
    
    Args:
        appointment_name: Appointment name
        discount_percentage: Discount percentage
        discount_amount: Discount amount
        gift_card: Gift card to use
        
    Returns:
        Dict with invoice creation result
    """
    from healthcare.healthcare.doctype.patient_appointment.patient_appointment import invoice_appointment
    
    try:
        appointment_doc = frappe.get_doc("Patient Appointment", appointment_name)
        
        # Validate gift card if provided
        if gift_card:
            validation = validate_gift_card(gift_card, appointment_doc.paid_amount)
            if not validation.get("valid"):
                return {
                    "success": False,
                    "message": validation.get("message"),
                    "validation_error": True
                }
        
        # Create invoice using existing healthcare function
        invoice_result = invoice_appointment(appointment_name, discount_percentage, discount_amount)
        
        # If invoice created successfully and gift card provided, allocate gift card
        if gift_card and appointment_doc.ref_sales_invoice:
            allocation_result = allocate_gift_card(
                gift_card=gift_card,
                amount=appointment_doc.paid_amount,
                sales_invoice=appointment_doc.ref_sales_invoice,
                appointment=appointment_name
            )
            
            if allocation_result.get("success"):
                # Update appointment with gift card info
                appointment_doc.db_set({
                    "use_gift_card": 1,
                    "selected_gift_card": gift_card,
                    "gift_card_allocated_amount": appointment_doc.paid_amount
                })
                
                return {
                    "success": True,
                    "message": _("Invoice created and gift card allocated successfully"),
                    "sales_invoice": appointment_doc.ref_sales_invoice,
                    "payment_entry": allocation_result.get("payment_entry")
                }
            else:
                # If gift card allocation failed, we should cancel the invoice
                # For now, return error (in production, you might want to cancel the invoice)
                return {
                    "success": False,
                    "message": _("Invoice created but gift card allocation failed: {0}").format(
                        allocation_result.get("message")
                    ),
                    "sales_invoice": appointment_doc.ref_sales_invoice,
                    "allocation_error": True
                }
        
        return {
            "success": True,
            "message": _("Invoice created successfully"),
            "sales_invoice": appointment_doc.ref_sales_invoice
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _("Gift Card Invoice Error"))
        return {
            "success": False,
            "message": _("Error creating invoice with gift card: {0}").format(str(e))
        }


@frappe.whitelist()
def get_gift_card_balance(gift_card: str) -> dict:
    """
    Get current balance of a gift card.
    
    Args:
        gift_card: Gift card name
        
    Returns:
        Dict with balance information
    """
    try:
        doc = frappe.get_doc("Eumaria Gift Card", gift_card)
        
        return {
            "success": True,
            "balance": doc.remaining_amount,
            "currency": frappe.defaults.get_global_default("currency"),
            "valid_until": doc.ends_on,
            "is_valid": (
                doc.docstatus == 1 and 
                not doc.disabled and
                (not doc.ends_on or getdate(doc.ends_on) >= getdate(nowdate())) and
                (not doc.starts_on or getdate(doc.starts_on) <= getdate(nowdate()))
            )
        }
        
    except frappe.DoesNotExistError:
        return {"success": False, "message": _("Gift card not found")}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _("Get Gift Card Balance Error"))
        return {"success": False, "message": _("Error getting gift card balance: {0}").format(str(e))}