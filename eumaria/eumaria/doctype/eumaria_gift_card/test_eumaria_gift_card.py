# Copyright (c) 2026, KAINOTOMO PH LTD and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate, nowdate, add_days, flt
import unittest


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = [
    "Company",
    "Customer",
    "Patient",
    "Mode of Payment",
    "Account",
    "Healthcare Settings",
    "Item",
    "Appointment Type",
    "Mode of Payment Account",
    "Healthcare Practitioner",
    "Sales Invoice",
    "Payment Entry"
]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]



class IntegrationTestEumariaGiftCard(IntegrationTestCase):
    """
    Integration tests for EumariaGiftCard.
    Use this class for testing interactions between multiple components.
    """

    def setUp(self):
        """Create required test fixtures before each test."""
        super().setUp()
        
        # Create test company if not exists
        if not frappe.db.exists("Company", "Test Company"):
            company = frappe.get_doc({
                "doctype": "Company",
                "company_name": "Test Company",
                "abbr": "TC",
                "default_currency": "USD",
                "country": "United States",
                "is_group": 0,
                "parent_company": ""
            })
            company.insert(ignore_permissions=True)
        
        # Create test customer
        if not frappe.db.exists("Customer", "Test Customer"):
            customer = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": "Test Customer",
                "customer_type": "Individual",
                "customer_group": "All Customer Groups",
                "territory": "All Territories"
            })
            customer.insert(ignore_permissions=True)
        
        # Create test patient linked to customer
        if not frappe.db.exists("Patient", "Test Patient"):
            patient = frappe.get_doc({
                "doctype": "Patient",
                "first_name": "Test",
                "last_name": "Patient",
                "sex": "Female",
                "customer": "Test Customer"
            })
            patient.insert(ignore_permissions=True)
        
        # Create mode of payment
        if not frappe.db.exists("Mode of Payment", "Test Mode of Payment"):
            mode_of_payment = frappe.get_doc({
                "doctype": "Mode of Payment",
                "mode_of_payment": "Test Mode of Payment",
                "type": "Cash"
            })
            mode_of_payment.insert(ignore_permissions=True)
        
        # Create accounts
        company = "Test Company"
        
        # Create receivable account
        if not frappe.db.exists("Account", "Debtors - TC"):
            receivable_account = frappe.get_doc({
                "doctype": "Account",
                "account_name": "Debtors",
                "parent_account": "Accounts Receivable - TC",
                "company": company,
                "account_type": "Receivable",
                "root_type": "Asset",
                "is_group": 0,
                "account_currency": "USD"
            })
            receivable_account.insert(ignore_permissions=True)
        
        # Create cash account for mode of payment
        if not frappe.db.exists("Account", "Cash - TC"):
            cash_account = frappe.get_doc({
                "doctype": "Account",
                "account_name": "Cash",
                "parent_account": "Cash In Hand - TC",
                "company": company,
                "account_type": "Cash",
                "root_type": "Asset",
                "is_group": 0,
                "account_currency": "USD"
            })
            cash_account.insert(ignore_permissions=True)
        
        # Link mode of payment to account
        if not frappe.db.exists("Mode of Payment Account", {
            "parent": "Test Mode of Payment",
            "company": company
        }):
            mode_of_payment_account = frappe.get_doc({
                "doctype": "Mode of Payment Account",
                "parent": "Test Mode of Payment",
                "parenttype": "Mode of Payment",
                "parentfield": "accounts",
                "company": company,
                "default_account": "Cash - TC"
            })
            mode_of_payment_account.insert(ignore_permissions=True)
        
        # Configure Healthcare Settings
        healthcare_settings = frappe.get_single("Healthcare Settings")
        healthcare_settings.show_payment_popup = 1
        healthcare_settings.enable_free_follow_ups = 0
        healthcare_settings.save()
        
        # Create billing item
        if not frappe.db.exists("Item", "Test Appointment Item"):
            item = frappe.get_doc({
                "doctype": "Item",
                "item_code": "Test Appointment Item",
                "item_name": "Test Appointment Item",
                "item_group": "Services",
                "is_stock_item": 0,
                "standard_rate": 100.0,
                "description": "Test appointment item for billing"
            })
            item.insert(ignore_permissions=True)
        
        # Create appointment type linked to item
        if not frappe.db.exists("Appointment Type", "Test Appointment Type"):
            appointment_type = frappe.get_doc({
                "doctype": "Appointment Type",
                "appointment_type": "Test Appointment Type",
                "default_duration": 30,
                "color": "#FF5733",
                "price_list_rate": 100.0,
                "item": "Test Appointment Item"
            })
            appointment_type.insert(ignore_permissions=True)
        
        # Create healthcare practitioner
        if not frappe.db.exists("Healthcare Practitioner", "Test Practitioner"):
            practitioner = frappe.get_doc({
                "doctype": "Healthcare Practitioner",
                "first_name": "Test",
                "last_name": "Practitioner",
                "practitioner_name": "Test Practitioner"
            })
            practitioner.insert(ignore_permissions=True)
        
        frappe.db.commit()

    def tearDown(self):
        """Clean up after each test."""
        frappe.db.rollback()
        super().tearDown()

    def _create_gift_card(self, patient="Test Patient", initial_amount=100.0, **kwargs):
        """Helper method to create a gift card for testing."""
        gift_card_data = {
            "doctype": "Eumaria Gift Card",
            "patient": patient,
            "initial_amount": initial_amount,
            "mode_of_payment": "Test Mode of Payment",
            "starts_on": getdate(),
            "ends_on": add_days(getdate(), 30),
            "disabled": 0
        }
        gift_card_data.update(kwargs)
        
        gift_card = frappe.get_doc(gift_card_data)
        gift_card.insert(ignore_permissions=True)
        return gift_card

    def _create_appointment(self, patient="Test Patient", paid_amount=100.0, **kwargs):
        """Helper method to create an appointment for testing."""
        appointment_data = {
            "doctype": "Patient Appointment",
            "patient": patient,
            "practitioner": "Test Practitioner",
            "appointment_date": getdate(),
            "appointment_time": "10:00:00",
            "appointment_type": "Test Appointment Type",
            "company": "Test Company",
            "paid_amount": paid_amount,
            "department": "OPD"
        }
        appointment_data.update(kwargs)
        
        appointment = frappe.get_doc(appointment_data)
        appointment.insert(ignore_permissions=True)
        return appointment

    def test_01_gift_card_creation_and_validation(self):
        """Test gift card creation and validation."""
        # Create gift card
        gift_card = self._create_gift_card(initial_amount=150.0)
        
        # Test validation
        self.assertEqual(gift_card.remaining_amount, 150.0)
        self.assertEqual(gift_card.initial_amount, 150.0)
        self.assertEqual(gift_card.patient, "Test Patient")
        self.assertEqual(gift_card.customer, "Test Customer")
        self.assertFalse(gift_card.disabled)
        
        # Test after_insert creates payment entry
        self.assertIsNotNone(gift_card.payment_entry)
        
        # Verify payment entry exists
        payment_entry = frappe.get_doc("Payment Entry", gift_card.payment_entry)
        self.assertEqual(payment_entry.party_type, "Customer")
        self.assertEqual(payment_entry.party, "Test Customer")
        self.assertEqual(payment_entry.paid_amount, 150.0)
        self.assertEqual(payment_entry.mode_of_payment, "Test Mode of Payment")
        
        # Submit gift card
        gift_card.submit()
        self.assertEqual(gift_card.docstatus, 1)
        
        # Verify payment entry is submitted
        payment_entry.reload()
        self.assertEqual(payment_entry.docstatus, 1)
        
        return gift_card

    def test_02_gift_card_submission_and_payment_entry_link(self):
        """Test gift card submission and payment entry linking."""
        gift_card = self._create_gift_card(initial_amount=200.0)
        
        # Submit gift card
        gift_card.submit()
        
        # Verify payment entry is linked and submitted
        self.assertIsNotNone(gift_card.payment_entry)
        payment_entry = frappe.get_doc("Payment Entry", gift_card.payment_entry)
        self.assertEqual(payment_entry.docstatus, 1)
        
        # Test remaining amount sync
        from eumaria.api.gift_card import sync_gift_card_remaining_amount
        available_amount = sync_gift_card_remaining_amount(gift_card.name)
        self.assertEqual(flt(available_amount, 2), 200.0)
        
        # Verify remaining_amount is updated
        gift_card.reload()
        self.assertEqual(flt(gift_card.remaining_amount, 2), 200.0)

    def test_03_gift_card_cancellation_and_payment_entry_cancel(self):
        """Test gift card cancellation and payment entry cancellation."""
        gift_card = self._create_gift_card(initial_amount=250.0)
        gift_card.submit()
        
        # Cancel gift card
        gift_card.cancel()
        self.assertEqual(gift_card.docstatus, 2)
        
        # Verify payment entry is cancelled
        payment_entry = frappe.get_doc("Payment Entry", gift_card.payment_entry)
        self.assertEqual(payment_entry.docstatus, 2)

    def test_04_gift_card_with_missing_patient_customer_link(self):
        """Test gift card creation with patient not linked to customer."""
        # Create patient without customer link
        patient_without_customer = frappe.get_doc({
            "doctype": "Patient",
            "first_name": "No",
            "last_name": "Customer",
            "sex": "Male"
        })
        patient_without_customer.insert(ignore_permissions=True)
        
        # Attempt to create gift card - should fail
        with self.assertRaises(frappe.ValidationError) as cm:
            self._create_gift_card(patient=patient_without_customer.name, initial_amount=100.0)
        
        self.assertIn("not linked to any customer", str(cm.exception))

    def test_05_gift_card_with_zero_or_negative_amount(self):
        """Test gift card creation with zero or negative amount."""
        # Test zero amount
        with self.assertRaises(frappe.ValidationError) as cm:
            self._create_gift_card(initial_amount=0)
        
        self.assertIn("greater than 0", str(cm.exception))
        
        # Test negative amount
        with self.assertRaises(frappe.ValidationError) as cm:
            self._create_gift_card(initial_amount=-50)
        
        self.assertIn("greater than 0", str(cm.exception))

    def test_06_gift_card_date_validity(self):
        """Test gift card date validity checks."""
        # Create gift card with past end date
        past_date = add_days(getdate(), -1)
        gift_card = self._create_gift_card(initial_amount=100.0, ends_on=past_date)
        gift_card.submit()
        
        # Validate gift card should fail due to expired date
        from eumaria.api.gift_card import validate_gift_card
        validation = validate_gift_card(gift_card.name, 50.0)
        self.assertFalse(validation["valid"])
        self.assertIn("expired", validation["message"])
        
        # Create gift card with future start date
        future_start = add_days(getdate(), 5)
        gift_card2 = self._create_gift_card(initial_amount=100.0, starts_on=future_start)
        gift_card2.submit()
        
        # Validate gift card should fail due to not yet valid
        validation = validate_gift_card(gift_card2.name, 50.0)
        self.assertFalse(validation["valid"])
        self.assertIn("not yet valid", validation["message"])

    def test_07_gift_card_disabled_status(self):
        """Test disabled gift card validation."""
        gift_card = self._create_gift_card(initial_amount=100.0, disabled=1)
        gift_card.submit()
        
        # Validate disabled gift card should fail
        from eumaria.api.gift_card import validate_gift_card
        validation = validate_gift_card(gift_card.name, 50.0)
        self.assertFalse(validation["valid"])
        self.assertIn("disabled", validation["message"])

    def test_08_gift_card_amendment(self):
        """Test gift card amendment workflow."""
        gift_card = self._create_gift_card(initial_amount=100.0)
        gift_card.submit()
        
        # Create amendment
        amended_gift_card = frappe.copy_doc(gift_card)
        amended_gift_card.amended_from = gift_card.name
        amended_gift_card.initial_amount = 150.0
        amended_gift_card.insert(ignore_permissions=True)
        
        # Amendment should not create new payment entry
        self.assertIsNone(amended_gift_card.payment_entry)
        
        # Submit amendment
        amended_gift_card.submit()
        
        # Original gift card should be cancelled
        gift_card.reload()
        self.assertEqual(gift_card.docstatus, 2)

    def test_09_payment_entry_unallocated_amount_sync(self):
        """Test payment entry unallocated amount sync with gift card."""
        gift_card = self._create_gift_card(initial_amount=300.0)
        gift_card.submit()
        
        # Get payment entry
        payment_entry = frappe.get_doc("Payment Entry", gift_card.payment_entry)
        
        # Initially unallocated amount should equal paid amount
        self.assertEqual(flt(payment_entry.unallocated_amount, 2), 300.0)
        
        # Manually allocate some amount (simulating invoice creation)
        payment_entry.unallocated_amount = 200.0
        payment_entry.save()
        
        # Sync should update gift card remaining amount
        from eumaria.api.gift_card import sync_gift_card_remaining_amount
        available_amount = sync_gift_card_remaining_amount(gift_card.name)
        
        self.assertEqual(flt(available_amount, 2), 200.0)
        gift_card.reload()
        self.assertEqual(flt(gift_card.remaining_amount, 2), 200.0)

    def test_10_get_gift_cards_for_customer(self):
        """Test retrieving gift cards for a customer."""
        # Create multiple gift cards
        gift_card1 = self._create_gift_card(initial_amount=100.0)
        gift_card1.submit()
        
        gift_card2 = self._create_gift_card(initial_amount=200.0)
        gift_card2.submit()
        
        # Create expired gift card
        past_date = add_days(getdate(), -1)
        gift_card3 = self._create_gift_card(initial_amount=50.0, ends_on=past_date)
        gift_card3.submit()
        
        # Get active gift cards for customer
        from eumaria.api.gift_card import get_gift_cards_for_customer
        active_cards = get_gift_cards_for_customer("Test Customer")
        
        # Should return only non-expired cards with positive balance
        self.assertEqual(len(active_cards), 2)
        
        # Check card details
        card_names = [card["name"] for card in active_cards]
        self.assertIn(gift_card1.name, card_names)
        self.assertIn(gift_card2.name, card_names)
        self.assertNotIn(gift_card3.name, card_names)
        
        # Check remaining amounts
        for card in active_cards:
            self.assertGreater(flt(card["remaining_amount"], 2), 0)

    def test_11_gift_card_payment_flow_with_sales_invoice(self):
        """Test complete gift card payment flow with Sales Invoice creation."""
        # Create gift card
        gift_card = self._create_gift_card(initial_amount=500.0)
        gift_card.submit()
        
        # Create appointment
        appointment = self._create_appointment(paid_amount=300.0)
        
        # Invoice appointment with gift card
        from eumaria.api.gift_card import invoice_appointment_with_gift_card
        result = invoice_appointment_with_gift_card(
            appointment_name=appointment.name,
            gift_card=gift_card.name,
            paid_amount=300.0
        )
        
        # Verify invoice creation was successful
        self.assertTrue(result["success"])
        self.assertIsNotNone(result["sales_invoice"])
        
        # Get created sales invoice
        sales_invoice = frappe.get_doc("Sales Invoice", result["sales_invoice"])
        
        # Verify sales invoice details
        self.assertEqual(sales_invoice.patient, "Test Patient")
        self.assertEqual(sales_invoice.customer, "Test Customer")
        self.assertEqual(sales_invoice.appointment, appointment.name)
        self.assertEqual(sales_invoice.company, "Test Company")
        
        # Verify advances table has exactly one entry linked to gift card payment entry
        self.assertEqual(len(sales_invoice.advances), 1)
        advance = sales_invoice.advances[0]
        self.assertEqual(advance.reference_type, "Payment Entry")
        self.assertEqual(advance.reference_name, gift_card.payment_entry)
        self.assertEqual(flt(advance.allocated_amount, 2), 300.0)
        
        # Verify gift card remaining amount is reduced
        gift_card.reload()
        self.assertEqual(flt(gift_card.remaining_amount, 2), 200.0)
        
        # Verify appointment fields are updated
        appointment.reload()
        self.assertEqual(appointment.invoiced, 1)
        self.assertEqual(appointment.ref_sales_invoice, sales_invoice.name)
        self.assertEqual(appointment.use_gift_card, 1)
        self.assertEqual(appointment.selected_gift_card, gift_card.name)
        self.assertEqual(flt(appointment.gift_card_allocated_amount, 2), 300.0)
        self.assertEqual(appointment.mode_of_payment, "")
        
        return gift_card, appointment, sales_invoice

    def test_12_regular_payment_flow_without_gift_card(self):
        """Test regular payment flow without gift card."""
        # Create appointment
        appointment = self._create_appointment(paid_amount=250.0, mode_of_payment="Test Mode of Payment")
        
        # Invoice appointment with regular payment (using overridden function)
        from eumaria.overrides.invoice_creation import invoice_appointment
        invoice_appointment(
            appointment_name=appointment.name,
            mode_of_payment="Test Mode of Payment",
            paid_amount=250.0
        )
        
        # Get created sales invoice from appointment
        appointment.reload()
        self.assertEqual(appointment.invoiced, 1)
        self.assertIsNotNone(appointment.ref_sales_invoice)
        
        sales_invoice = frappe.get_doc("Sales Invoice", appointment.ref_sales_invoice)
        
        # Verify sales invoice details
        self.assertEqual(sales_invoice.patient, "Test Patient")
        self.assertEqual(sales_invoice.customer, "Test Customer")
        self.assertEqual(sales_invoice.appointment, appointment.name)
        
        # Verify no advances allocated (regular payment)
        self.assertEqual(len(sales_invoice.advances), 0)
        
        # Verify appointment fields
        self.assertEqual(appointment.use_gift_card, 0)
        self.assertEqual(appointment.selected_gift_card, "")
        self.assertEqual(flt(appointment.gift_card_allocated_amount, 2), 0)
        self.assertEqual(appointment.mode_of_payment, "Test Mode of Payment")

    def test_13_gift_card_payment_with_percentage_discount(self):
        """Test gift card payment with percentage discount."""
        # Create gift card
        gift_card = self._create_gift_card(initial_amount=400.0)
        gift_card.submit()
        
        # Create appointment with base amount
        appointment = self._create_appointment(paid_amount=400.0)
        
        # Invoice with 25% discount
        from eumaria.api.gift_card import invoice_appointment_with_gift_card
        result = invoice_appointment_with_gift_card(
            appointment_name=appointment.name,
            gift_card=gift_card.name,
            discount_percentage=25.0  # 25% discount
        )
        
        self.assertTrue(result["success"])
        
        # Get sales invoice
        sales_invoice = frappe.get_doc("Sales Invoice", result["sales_invoice"])
        
        # Verify discount applied
        self.assertEqual(flt(sales_invoice.additional_discount_percentage, 2), 25.0)
        
        # Calculate expected payable amount: 400 - 25% = 300
        expected_payable = 300.0
        
        # Verify advance allocation matches discounted amount
        advance = sales_invoice.advances[0]
        self.assertEqual(flt(advance.allocated_amount, 2), expected_payable)
        
        # Verify gift card balance reduced by discounted amount
        gift_card.reload()
        self.assertEqual(flt(gift_card.remaining_amount, 2), 100.0)  # 400 - 300 = 100

    def test_14_gift_card_payment_with_fixed_discount(self):
        """Test gift card payment with fixed amount discount."""
        # Create gift card
        gift_card = self._create_gift_card(initial_amount=500.0)
        gift_card.submit()
        
        # Create appointment
        appointment = self._create_appointment(paid_amount=500.0)
        
        # Invoice with $100 discount
        from eumaria.api.gift_card import invoice_appointment_with_gift_card
        result = invoice_appointment_with_gift_card(
            appointment_name=appointment.name,
            gift_card=gift_card.name,
            discount_amount=100.0
        )
        
        self.assertTrue(result["success"])
        
        # Get sales invoice
        sales_invoice = frappe.get_doc("Sales Invoice", result["sales_invoice"])
        
        # Verify discount applied
        self.assertEqual(flt(sales_invoice.discount_amount, 2), 100.0)
        
        # Expected payable amount: 500 - 100 = 400
        expected_payable = 400.0
        
        # Verify advance allocation
        advance = sales_invoice.advances[0]
        self.assertEqual(flt(advance.allocated_amount, 2), expected_payable)
        
        # Verify gift card balance
        gift_card.reload()
        self.assertEqual(flt(gift_card.remaining_amount, 2), 100.0)  # 500 - 400 = 100

    def test_15_insufficient_gift_card_balance(self):
        """Test gift card payment with insufficient balance."""
        # Create gift card with small balance
        gift_card = self._create_gift_card(initial_amount=100.0)
        gift_card.submit()
        
        # Create appointment with larger amount
        appointment = self._create_appointment(paid_amount=300.0)
        
        # Attempt to invoice - should fail
        from eumaria.api.gift_card import invoice_appointment_with_gift_card
        result = invoice_appointment_with_gift_card(
            appointment_name=appointment.name,
            gift_card=gift_card.name,
            paid_amount=300.0
        )
        
        # Should fail with insufficient balance error
        self.assertFalse(result["success"])
        self.assertIn("Insufficient balance", result["message"])
        
        # Appointment should not be invoiced
        appointment.reload()
        self.assertEqual(appointment.invoiced, 0)
        self.assertIsNone(appointment.ref_sales_invoice)

    def test_16_gift_card_validation_with_skip_balance_check(self):
        """Test gift card validation with skip_balance_check parameter."""
        # Create gift card with small balance
        gift_card = self._create_gift_card(initial_amount=50.0)
        gift_card.submit()
        
        # Validate with amount larger than balance but skip_balance_check=True
        from eumaria.api.gift_card import validate_gift_card
        validation = validate_gift_card(gift_card.name, 100.0, skip_balance_check=True)
        
        # Should pass validation (only checking status, dates, etc.)
        self.assertTrue(validation["valid"])
        
        # Validate without skip_balance_check - should fail
        validation = validate_gift_card(gift_card.name, 100.0, skip_balance_check=False)
        self.assertFalse(validation["valid"])
        self.assertIn("Insufficient balance", validation["message"])

    def test_17_mixed_payment_method_validation(self):
        """Test validation when both gift card and regular payment method are used."""
        # Create gift card
        gift_card = self._create_gift_card(initial_amount=200.0)
        gift_card.submit()
        
        # Create appointment with both mode_of_payment and use_gift_card
        appointment = self._create_appointment(
            paid_amount=200.0,
            mode_of_payment="Test Mode of Payment",
            use_gift_card=1,
            selected_gift_card=gift_card.name
        )
        
        # Attempt to invoice - should fail due to mixed payment methods
        from eumaria.api.gift_card import invoice_appointment_with_gift_card
        result = invoice_appointment_with_gift_card(
            appointment_name=appointment.name,
            gift_card=gift_card.name
        )
        
        self.assertFalse(result["success"])
        self.assertIn("Cannot use both gift card and regular payment method", result["message"])

    def test_18_appointment_already_invoiced(self):
        """Test gift card payment for already invoiced appointment."""
        # Create gift card
        gift_card = self._create_gift_card(initial_amount=200.0)
        gift_card.submit()
        
        # Create and invoice appointment with regular payment first
        appointment = self._create_appointment(paid_amount=200.0, mode_of_payment="Test Mode of Payment")
        
        from eumaria.overrides.invoice_creation import invoice_appointment
        invoice_appointment(
            appointment_name=appointment.name,
            mode_of_payment="Test Mode of Payment",
            paid_amount=200.0
        )
        
        appointment.reload()
        self.assertEqual(appointment.invoiced, 1)
        
        # Attempt to invoice again with gift card - should fail
        from eumaria.api.gift_card import invoice_appointment_with_gift_card
        result = invoice_appointment_with_gift_card(
            appointment_name=appointment.name,
            gift_card=gift_card.name
        )
        
        self.assertFalse(result["success"])
        self.assertIn("Invoice cannot be created", result["message"])

    def test_19_sales_invoice_cancellation_and_balance_restoration(self):
        """Test Sales Invoice cancellation and gift card balance restoration."""
        # Create gift card and invoice appointment
        gift_card, appointment, sales_invoice = self.test_11_gift_card_payment_flow_with_sales_invoice()
        
        # Verify initial state
        self.assertEqual(flt(gift_card.remaining_amount, 2), 200.0)  # 500 - 300 = 200
        
        # Cancel sales invoice
        sales_invoice.cancel()
        
        # Verify gift card balance is restored
        gift_card.reload()
        self.assertEqual(flt(gift_card.remaining_amount, 2), 500.0)  # Restored to original
        
        # Verify appointment fields are cleared
        appointment.reload()
        self.assertEqual(appointment.invoiced, 0)
        self.assertEqual(appointment.ref_sales_invoice, "")
        self.assertEqual(appointment.use_gift_card, 0)
        self.assertEqual(appointment.selected_gift_card, "")
        self.assertEqual(flt(appointment.gift_card_allocated_amount, 2), 0)

    def test_20_gift_card_balance_restoration_function(self):
        """Test gift card balance restoration function."""
        # Create gift card
        gift_card = self._create_gift_card(initial_amount=300.0)
        gift_card.submit()
        
        # Simulate allocation by reducing payment entry unallocated amount
        payment_entry = frappe.get_doc("Payment Entry", gift_card.payment_entry)
        payment_entry.unallocated_amount = 150.0  # Simulate 150 allocated
        payment_entry.save()
        
        # Sync gift card - should reflect reduced balance
        from eumaria.api.gift_card import sync_gift_card_remaining_amount
        available_amount = sync_gift_card_remaining_amount(gift_card.name)
        self.assertEqual(flt(available_amount, 2), 150.0)
        
        # Test restore_gift_card function (which just syncs)
        from eumaria.api.gift_card import restore_gift_card
        result = restore_gift_card(gift_card.name, 150.0)
        
        self.assertTrue(result["success"])
        # restore_gift_card just syncs, so balance should still be 150
        self.assertEqual(flt(result["new_balance"], 2), 150.0)

    def test_21_concurrent_gift_card_allocations(self):
        """Test multiple appointments using the same gift card."""
        # Create gift card with large balance
        gift_card = self._create_gift_card(initial_amount=1000.0)
        gift_card.submit()
        
        # Create first appointment and invoice
        appointment1 = self._create_appointment(paid_amount=300.0)
        from eumaria.api.gift_card import invoice_appointment_with_gift_card
        result1 = invoice_appointment_with_gift_card(
            appointment_name=appointment1.name,
            gift_card=gift_card.name
        )
        self.assertTrue(result1["success"])
        
        # Verify balance after first allocation
        gift_card.reload()
        self.assertEqual(flt(gift_card.remaining_amount, 2), 700.0)
        
        # Create second appointment and invoice
        appointment2 = self._create_appointment(paid_amount=400.0)
        result2 = invoice_appointment_with_gift_card(
            appointment_name=appointment2.name,
            gift_card=gift_card.name
        )
        self.assertTrue(result2["success"])
        
        # Verify balance after second allocation
        gift_card.reload()
        self.assertEqual(flt(gift_card.remaining_amount, 2), 300.0)
        
        # Create third appointment with amount exceeding remaining balance
        appointment3 = self._create_appointment(paid_amount=400.0)
        result3 = invoice_appointment_with_gift_card(
            appointment_name=appointment3.name,
            gift_card=gift_card.name
        )
        
        # Should fail due to insufficient balance
        self.assertFalse(result3["success"])
        self.assertIn("Insufficient balance", result3["message"])

    def test_22_get_gift_card_balance_function(self):
        """Test get_gift_card_balance API function."""
        # Create valid gift card
        gift_card = self._create_gift_card(initial_amount=250.0)
        gift_card.submit()
        
        from eumaria.api.gift_card import get_gift_card_balance
        result = get_gift_card_balance(gift_card.name)
        
        self.assertTrue(result["success"])
        self.assertEqual(flt(result["balance"], 2), 250.0)
        self.assertEqual(result["currency"], "USD")
        self.assertTrue(result["is_valid"])
        
        # Create expired gift card
        past_date = add_days(getdate(), -1)
        expired_gift_card = self._create_gift_card(
            initial_amount=100.0,
            ends_on=past_date
        )
        expired_gift_card.submit()
        
        result = get_gift_card_balance(expired_gift_card.name)
        self.assertTrue(result["success"])
        self.assertFalse(result["is_valid"])

    def test_23_allocate_gift_card_function(self):
        """Test allocate_gift_card API function."""
        # Create gift card
        gift_card = self._create_gift_card(initial_amount=350.0)
        gift_card.submit()
        
        from eumaria.api.gift_card import allocate_gift_card
        result = allocate_gift_card(gift_card.name, 200.0)
        
        # allocate_gift_card just syncs balance
        self.assertTrue(result["success"])
        self.assertEqual(flt(result["new_balance"], 2), 350.0)  # No actual allocation
        
        # Test with insufficient balance
        result = allocate_gift_card(gift_card.name, 500.0)
        self.assertFalse(result["success"])
        self.assertIn("Insufficient balance", result["message"])

    def test_24_edge_case_zero_payable_amount(self):
        """Test edge case where payable amount is zero (100% discount)."""
        # Create gift card
        gift_card = self._create_gift_card(initial_amount=100.0)
        gift_card.submit()
        
        # Create appointment
        appointment = self._create_appointment(paid_amount=100.0)
        
        # Invoice with 100% discount
        from eumaria.api.gift_card import invoice_appointment_with_gift_card
        result = invoice_appointment_with_gift_card(
            appointment_name=appointment.name,
            gift_card=gift_card.name,
            discount_percentage=100.0
        )
        
        # Should succeed with zero payable amount
        self.assertTrue(result["success"])
        
        # Get sales invoice
        sales_invoice = frappe.get_doc("Sales Invoice", result["sales_invoice"])
        
        # Verify no advance allocated (zero amount)
        self.assertEqual(len(sales_invoice.advances), 0)
        
        # Gift card balance should remain unchanged
        gift_card.reload()
        self.assertEqual(flt(gift_card.remaining_amount, 2), 100.0)

    def test_25_edge_case_negative_payable_amount(self):
        """Test edge case where discount exceeds base amount."""
        # Create gift card
        gift_card = self._create_gift_card(initial_amount=100.0)
        gift_card.submit()
        
        # Create appointment
        appointment = self._create_appointment(paid_amount=100.0)
        
        # Invoice with discount larger than base amount
        from eumaria.api.gift_card import invoice_appointment_with_gift_card
        result = invoice_appointment_with_gift_card(
            appointment_name=appointment.name,
            gift_card=gift_card.name,
            discount_amount=150.0  # More than base amount
        )
        
        # Should succeed with zero payable amount (clamped)
        self.assertTrue(result["success"])
        
        # Get sales invoice
        sales_invoice = frappe.get_doc("Sales Invoice", result["sales_invoice"])
        
        # Verify no advance allocated
        self.assertEqual(len(sales_invoice.advances), 0)
        
        # Gift card balance should remain unchanged
        gift_card.reload()
        self.assertEqual(flt(gift_card.remaining_amount, 2), 100.0)

