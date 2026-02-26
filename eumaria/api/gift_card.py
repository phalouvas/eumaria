# Copyright (c) 2026, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate


def get_available_gift_card_amount(gift_card_doc) -> float:
    """Return currently available amount from linked Payment Entry advance."""
    if not gift_card_doc.payment_entry:
        return flt(gift_card_doc.remaining_amount) or 0

    result = frappe.db.get_value(
        "Payment Entry", gift_card_doc.payment_entry, ["unallocated_amount", "docstatus"]
    )
    
    if not result:
        return 0
    
    unallocated_amount, docstatus = result
    
    if docstatus != 1:
        return 0
    
    return flt(unallocated_amount) or 0

    return flt(unallocated_amount)


def sync_gift_card_remaining_amount(gift_card: str) -> float:
    """Sync gift card remaining_amount with Payment Entry unallocated amount."""
    doc = frappe.get_doc("Eumaria Gift Card", gift_card)
    available_amount = get_available_gift_card_amount(doc)

    if flt(doc.remaining_amount or 0) != available_amount:
        doc.db_set("remaining_amount", available_amount)

    return available_amount


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
        fields=["name", "remaining_amount", "ends_on", "initial_amount", "mode_of_payment", "payment_entry"],
        order_by="ends_on asc"
    )

    active_cards = []
    for card in gift_cards:
        available_amount = get_available_gift_card_amount(frappe._dict(card))
        if available_amount <= 0:
            continue

        if flt(card.get("remaining_amount")) != available_amount:
            frappe.db.set_value("Eumaria Gift Card", card["name"], "remaining_amount", available_amount)

        card["remaining_amount"] = available_amount
        card["display"] = f"{card['name']} (Balance: {available_amount}, Valid until: {card['ends_on']})"
        active_cards.append(card)

    return active_cards


@frappe.whitelist()
def validate_gift_card(gift_card: str, amount: float, skip_balance_check: bool = False) -> dict:
    """
    Validate if a gift card can be used for a payment.

    Args:
        gift_card: Gift card name
        amount: Amount to pay
        skip_balance_check: If True, skip balance validation (only check status, dates, etc.)

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
        
        available_amount = sync_gift_card_remaining_amount(doc.name)

        # Check balance
        if not skip_balance_check and available_amount < amount:
            return {
                "valid": False,
                "message": _("Insufficient balance. Available: {0}, Required: {1}").format(
                    available_amount, amount
                )
            }
        
        return {
            "valid": True,
            "message": _("Gift card validated successfully"),
            "remaining_amount": available_amount,
            "mode_of_payment": doc.mode_of_payment
        }
        
    except frappe.DoesNotExistError:
        return {"valid": False, "message": _("Gift card not found")}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _("Gift Card Validation Error"))
        return {"valid": False, "message": _("Error validating gift card: {0}").format(str(e))}


@frappe.whitelist()
def allocate_gift_card(gift_card: str, amount: float, sales_invoice: str = None, appointment: str = None) -> dict:
    """Backward-compatible helper: returns current balance after syncing with linked advance."""
    try:
        amount = flt(amount)
        if amount < 0:
            return {"success": False, "message": _("Amount cannot be negative")}

        validation = validate_gift_card(gift_card, amount)
        if not validation.get("valid"):
            return {"success": False, "message": validation.get("message")}

        new_balance = sync_gift_card_remaining_amount(gift_card)
        return {
            "success": True,
            "message": _("Gift card balance synced successfully"),
            "new_balance": new_balance,
            "sales_invoice": sales_invoice,
            "appointment": appointment,
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _("Gift Card Allocation Error"))
        return {
            "success": False,
            "message": _("Error allocating gift card: {0}").format(str(e))
        }


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
        new_balance = sync_gift_card_remaining_amount(gift_card)

        return {
            "success": True,
            "message": _("Gift card balance restored successfully"),
            "new_balance": new_balance
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _("Gift Card Restoration Error"))
        return {
            "success": False,
            "message": _("Error restoring gift card: {0}").format(str(e))
        }


def create_gift_card_sales_invoice(
    appointment_doc,
    gift_card_doc,
    discount_percentage: float = 0,
    discount_amount: float = 0,
):
    """Create Sales Invoice and allocate only the linked gift-card Payment Entry advance."""
    from healthcare.healthcare.doctype.healthcare_settings.healthcare_settings import get_receivable_account
    from healthcare.healthcare.doctype.patient_appointment.patient_appointment import get_appointment_item

    sales_invoice = frappe.new_doc("Sales Invoice")
    sales_invoice.patient = appointment_doc.patient
    sales_invoice.customer = frappe.get_value("Patient", appointment_doc.patient, "customer")
    sales_invoice.appointment = appointment_doc.name
    sales_invoice.due_date = getdate()
    sales_invoice.company = appointment_doc.company
    sales_invoice.debit_to = get_receivable_account(appointment_doc.company)

    item = sales_invoice.append("items", {})
    item = get_appointment_item(appointment_doc, item)

    # Get paid amount from appointment, default to 0 if None
    appointment_paid_amount = flt(appointment_doc.paid_amount) or 0
    paid_amount = appointment_paid_amount
    
    discount_percentage_val = flt(discount_percentage) or 0
    discount_amount_val = flt(discount_amount) or 0
    
    if discount_percentage_val:
        sales_invoice.additional_discount_percentage = discount_percentage_val
        paid_amount = appointment_paid_amount - (
            appointment_paid_amount * (discount_percentage_val / 100)
        )

    if discount_amount_val:
        sales_invoice.discount_amount = discount_amount_val
        paid_amount = appointment_paid_amount - discount_amount_val

    paid_amount = max(flt(paid_amount), 0)

    sales_invoice.allocate_advances_automatically = 0
    sales_invoice.set_missing_values(for_validate=True)
    sales_invoice.calculate_taxes_and_totals()
    sales_invoice.set_advances()

    matching_advance = next(
        (
            advance
            for advance in sales_invoice.advances
            if advance.reference_type == "Payment Entry"
            and advance.reference_name == gift_card_doc.payment_entry
        ),
        None,
    )

    if not matching_advance:
        frappe.throw(
            _("No available advance was found for Gift Card {0}.").format(gift_card_doc.name)
        )

    if flt(matching_advance.advance_amount) < paid_amount:
        frappe.throw(
            _("Insufficient gift card balance. Available: {0}, Required: {1}").format(
                matching_advance.advance_amount,
                paid_amount,
            )
        )

    sales_invoice.set("advances", [])
    sales_invoice.append(
        "advances",
        {
            "reference_type": matching_advance.reference_type,
            "reference_name": matching_advance.reference_name,
            "reference_row": matching_advance.reference_row,
            "remarks": matching_advance.remarks,
            "advance_amount": matching_advance.advance_amount,
            "allocated_amount": paid_amount,
            "ref_exchange_rate": matching_advance.ref_exchange_rate,
            "difference_posting_date": sales_invoice.posting_date,
        },
    )

    sales_invoice.flags.ignore_mandatory = True
    sales_invoice.save(ignore_permissions=True)
    sales_invoice.submit()

    return sales_invoice, paid_amount


@frappe.whitelist()
def invoice_appointment_with_gift_card(appointment_name: str, discount_percentage: float = 0, discount_amount: float = 0, 
                                      gift_card: str = None, paid_amount: float = None) -> dict:
    """
    Create invoice for appointment with gift card payment.
    
    Args:
        appointment_name: Appointment name
        discount_percentage: Discount percentage
        discount_amount: Discount amount
        gift_card: Gift card to use
        paid_amount: Paid amount (optional, defaults to appointment.paid_amount)
        
    Returns:
        Dict with invoice creation result
    """
    from healthcare.healthcare.doctype.fee_validity.fee_validity import check_fee_validity, get_fee_validity
    from healthcare.healthcare.doctype.patient_appointment.patient_appointment import update_fee_validity
    
    try:
        appointment_doc = frappe.get_doc("Patient Appointment", appointment_name)

        if appointment_doc.mode_of_payment:
            return {
                "success": False,
                "message": _("Cannot use both gift card and regular payment method. Please choose one."),
                "validation_error": True,
            }

        gift_card_name = gift_card or appointment_doc.selected_gift_card
        if not gift_card_name:
            return {
                "success": False,
                "message": _("Please select a gift card when using gift card payment."),
                "validation_error": True,
            }

        # Use provided paid_amount or fall back to appointment.paid_amount
        base_amount = flt(paid_amount) if paid_amount is not None else flt(appointment_doc.paid_amount)
        
        # Ensure base_amount is not None
        if base_amount is None:
            base_amount = 0
        
        # Compute discounted amount
        discount_amt = flt(discount_amount) or 0
        discount_percentage_val = flt(discount_percentage) or 0
        
        if not discount_amt and discount_percentage_val:
            discount_amt = base_amount * discount_percentage_val / 100

        payable_amount = base_amount - discount_amt
        if payable_amount < 0:
            payable_amount = 0

        validation = validate_gift_card(gift_card_name, payable_amount)
        if not validation.get("valid"):
            return {
                "success": False,
                "message": validation.get("message"),
                "validation_error": True,
            }

        settings = frappe.get_single("Healthcare Settings")
        if settings.enable_free_follow_ups:
            fee_validity = check_fee_validity(appointment_doc)

            if fee_validity and fee_validity.status != "Active":
                fee_validity = None
            elif not fee_validity and get_fee_validity(appointment_doc.name, appointment_doc.appointment_date):
                return {
                    "success": True,
                    "message": _("Fee validity exists. No invoice created."),
                }
        else:
            fee_validity = None

        if not settings.show_payment_popup or appointment_doc.invoiced or fee_validity:
            return {
                "success": False,
                "message": _("Invoice cannot be created for this appointment."),
                "validation_error": True,
            }

        gift_card_doc = frappe.get_doc("Eumaria Gift Card", gift_card_name)
        sales_invoice, allocated_amount = create_gift_card_sales_invoice(
            appointment_doc,
            gift_card_doc,
            discount_percentage,
            discount_amount,
        )

        appointment_doc.db_set(
            {
                "invoiced": 1,
                "ref_sales_invoice": sales_invoice.name,
                "paid_amount": allocated_amount,
                "use_gift_card": 1,
                "selected_gift_card": gift_card_name,
                "gift_card_allocated_amount": allocated_amount,
                "mode_of_payment": "",
            }
        )

        sync_gift_card_remaining_amount(gift_card_name)
        update_fee_validity(appointment_doc)
        appointment_doc.notify_update()

        return {
            "success": True,
            "message": _("Invoice created and gift card allocated successfully"),
            "sales_invoice": sales_invoice.name,
            "payment_entry": gift_card_doc.payment_entry,
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
        available_amount = sync_gift_card_remaining_amount(gift_card)

        return {
            "success": True,
            "balance": available_amount,
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