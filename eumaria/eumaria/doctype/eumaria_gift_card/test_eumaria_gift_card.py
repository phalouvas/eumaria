# Copyright (c) 2026, KAINOTOMO PH LTD and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.utils import getdate, nowdate, add_days, flt
import unittest
from unittest.mock import patch, MagicMock, Mock



class TestEumariaGiftCard(unittest.TestCase):
    """
    Unit tests for EumariaGiftCard doctype.
    Uses mocking to isolate tests from database dependencies.
    """

    def _create_mock_gift_card(self, **kwargs):
        """Create a mock gift card document for testing."""
        defaults = {
            "name": "TEST-GC-001",
            "patient": "Test Patient",
            "customer": "Test Customer",
            "initial_amount": 100.0,
            "remaining_amount": 100.0,
            "mode_of_payment": "Test Mode of Payment",
            "payment_entry": "TEST-PE-001",
            "starts_on": getdate(),
            "ends_on": add_days(getdate(), 30),
            "disabled": 0,
            "docstatus": 0,
            "is_new": lambda: True,
            "get": lambda key, default=None: kwargs.get(key, defaults.get(key, default)),
            "db_set": MagicMock(),
            "reload": MagicMock(),
            "submit": MagicMock(),
            "cancel": MagicMock()
        }
        defaults.update(kwargs)
        
        mock_doc = MagicMock()
        for key, value in defaults.items():
            if callable(value):
                setattr(mock_doc, key, value)
            else:
                setattr(mock_doc, key, value)
        
        return mock_doc

    def test_01_gift_card_validate_method(self):
        """Test gift card validate method."""
        # Test new gift card sets remaining_amount equal to initial_amount
        with patch.object(frappe, 'get_value') as mock_get_value, \
             patch.object(frappe, 'log_error') as mock_log_error:
            
            mock_get_value.return_value = "Test Customer"
            
            # Create mock gift card
            gift_card = self._create_mock_gift_card(
                initial_amount=150.0,
                remaining_amount=None,
                patient="Test Patient",
                customer=None
            )
            
            # Mock is_new() to return True
            gift_card.is_new = MagicMock(return_value=True)
            
            # Call validate method
            from eumaria.eumaria.doctype.eumaria_gift_card.eumaria_gift_card import EumariaGiftCard
            doc = EumariaGiftCard(gift_card)
            doc.validate()
            
            # Verify remaining_amount was set to initial_amount
            self.assertEqual(gift_card.remaining_amount, 150.0)
            
            # Verify customer was populated from patient
            self.assertEqual(gift_card.customer, "Test Customer")
            
            # Test validation error when patient has no customer
            mock_get_value.return_value = None
            gift_card.customer = None
            
            with self.assertRaises(frappe.ValidationError) as cm:
                doc.validate()
            
            self.assertIn("not linked to any customer", str(cm.exception))
            
            # Test validation error when patient is missing
            gift_card.patient = None
            with self.assertRaises(frappe.ValidationError) as cm:
                doc.validate()
            
            self.assertIn("Patient is required", str(cm.exception))

    def test_02_gift_card_after_insert_creates_payment_entry(self):
        """Test gift card after_insert method creates payment entry."""
        with patch.object(frappe, 'get_value') as mock_get_value, \
             patch.object(frappe, 'get_doc') as mock_get_doc, \
             patch.object(frappe, 'log_error') as mock_log_error, \
             patch('frappe.defaults.get_defaults') as mock_get_defaults:
            
            # Mock defaults
            mock_defaults = MagicMock()
            mock_defaults.company = "Test Company"
            mock_get_defaults.return_value = mock_defaults
            
            # Mock get_value for patient customer lookup
            mock_get_value.side_effect = lambda doctype, name, fieldname: {
                ("Patient", "Test Patient", "customer"): "Test Customer",
                ("Mode of Payment Account", {"parent": "Test Mode of Payment", "company": "Test Company"}, "default_account"): "Cash - TC"
            }.get((doctype, name, fieldname) if isinstance(name, str) else (doctype, tuple(name.items()), fieldname))
            
            # Create mock payment entry
            mock_payment_entry = MagicMock()
            mock_payment_entry.name = "TEST-PE-001"
            mock_payment_entry.insert = MagicMock()
            mock_get_doc.return_value = mock_payment_entry
            
            # Create mock gift card
            gift_card = self._create_mock_gift_card(
                initial_amount=200.0,
                payment_entry=None,
                amended_from=None
            )
            
            # Call after_insert method
            from eumaria.eumaria.doctype.eumaria_gift_card.eumaria_gift_card import EumariaGiftCard
            doc = EumariaGiftCard(gift_card)
            doc.after_insert()
            
            # Verify payment entry was created and linked
            mock_get_doc.assert_called_once()
            mock_payment_entry.insert.assert_called_once_with(ignore_permissions=True)
            gift_card.db_set.assert_called_once_with("payment_entry", "TEST-PE-001")
            
            # Test validation errors
            # Test missing patient
            gift_card.patient = None
            with self.assertRaises(frappe.ValidationError) as cm:
                doc.after_insert()
            self.assertIn("Patient is required", str(cm.exception))
            
            # Test missing customer
            gift_card.patient = "Test Patient"
            gift_card.customer = None
            mock_get_value.side_effect = lambda doctype, name, fieldname: None
            with self.assertRaises(frappe.ValidationError) as cm:
                doc.after_insert()
            self.assertIn("Customer is required", str(cm.exception))
            
            # Test zero initial amount
            gift_card.customer = "Test Customer"
            gift_card.initial_amount = 0
            with self.assertRaises(frappe.ValidationError) as cm:
                doc.after_insert()
            self.assertIn("greater than 0", str(cm.exception))

    def test_03_gift_card_on_submit_and_on_cancel_methods(self):
        """Test gift card on_submit and on_cancel methods."""
        # Test on_submit method
        with patch.object(frappe, 'get_doc') as mock_get_doc, \
             patch.object(frappe, 'log_error') as mock_log_error:
            
            # Create mock payment entry
            mock_payment_entry = MagicMock()
            mock_payment_entry.name = "TEST-PE-001"
            mock_payment_entry.docstatus = 0
            mock_payment_entry.submit = MagicMock()
            mock_payment_entry.cancel = MagicMock()
            mock_payment_entry.reload = MagicMock()
            
            # Create mock gift card
            gift_card = self._create_mock_gift_card(
                payment_entry="TEST-PE-001",
                docstatus=0
            )
            
            mock_get_doc.return_value = mock_payment_entry
            
            # Call on_submit method
            from eumaria.eumaria.doctype.eumaria_gift_card.eumaria_gift_card import EumariaGiftCard
            doc = EumariaGiftCard(gift_card)
            doc.on_submit()
            
            # Verify payment entry was submitted
            mock_payment_entry.submit.assert_called_once()
            
            # Test error when payment entry doesn't exist
            mock_get_doc.side_effect = frappe.DoesNotExistError
            with self.assertRaises(frappe.ValidationError) as cm:
                doc.on_submit()
            self.assertIn("does not exist", str(cm.exception))
            
            # Test on_cancel method
            mock_payment_entry = MagicMock()
            mock_payment_entry.name = "TEST-PE-001"
            mock_payment_entry.docstatus = 1
            mock_payment_entry.submit = MagicMock()
            mock_payment_entry.cancel = MagicMock()
            mock_payment_entry.reload = MagicMock()
            
            mock_get_doc.return_value = mock_payment_entry
            mock_get_doc.side_effect = None
            
            doc.on_cancel()
            
            # Verify payment entry was cancelled
            mock_payment_entry.cancel.assert_called_once()
            
            # Test on_cancel with no payment entry
            gift_card.payment_entry = None
            doc.on_cancel()  # Should not raise error
            
            # Test on_cancel with cancelled payment entry
            gift_card.payment_entry = "TEST-PE-001"
            mock_payment_entry.docstatus = 2  # Already cancelled
            doc.on_cancel()
            # Should not call cancel on already cancelled payment entry

    def test_04_api_get_available_gift_card_amount(self):
        """Test get_available_gift_card_amount API function."""
        from eumaria.api.gift_card import get_available_gift_card_amount
        
        # Test with payment entry
        with patch.object(frappe.db, 'get_value') as mock_get_value:
            mock_get_value.return_value = (150.0, 1)  # unallocated_amount, docstatus
            
            gift_card = self._create_mock_gift_card(payment_entry="TEST-PE-001")
            amount = get_available_gift_card_amount(gift_card)
            
            self.assertEqual(flt(amount, 2), 150.0)
            mock_get_value.assert_called_once_with(
                "Payment Entry", "TEST-PE-001", ["unallocated_amount", "docstatus"]
            )
        
        # Test without payment entry
        gift_card = self._create_mock_gift_card(payment_entry=None, remaining_amount=200.0)
        amount = get_available_gift_card_amount(gift_card)
        self.assertEqual(flt(amount, 2), 200.0)
        
        # Test with payment entry but draft status
        with patch.object(frappe.db, 'get_value') as mock_get_value:
            mock_get_value.return_value = (150.0, 0)  # docstatus = 0 (draft)
            
            gift_card = self._create_mock_gift_card(payment_entry="TEST-PE-001")
            amount = get_available_gift_card_amount(gift_card)
            
            self.assertEqual(flt(amount, 2), 0.0)

    def test_05_api_sync_gift_card_remaining_amount(self):
        """Test sync_gift_card_remaining_amount API function."""
        from eumaria.api.gift_card import sync_gift_card_remaining_amount
        
        gift_card_name = "TEST-GC-SYNC"
        
        with patch.object(frappe, 'get_doc') as mock_get_doc, \
             patch('eumaria.api.gift_card.get_available_gift_card_amount') as mock_get_available:
            
            # Create mock gift card
            mock_gift_card = self._create_mock_gift_card(
                name=gift_card_name,
                remaining_amount=200.0
            )
            
            mock_get_doc.return_value = mock_gift_card
            mock_get_available.return_value = 150.0  # Different from remaining_amount
            
            # Sync when amounts differ
            result = sync_gift_card_remaining_amount(gift_card_name)
            
            self.assertEqual(flt(result, 2), 150.0)
            mock_gift_card.db_set.assert_called_once_with("remaining_amount", 150.0)
            
            # Sync when amounts are equal
            mock_get_available.return_value = 200.0  # Same as remaining_amount
            mock_gift_card.db_set.reset_mock()
            
            result = sync_gift_card_remaining_amount(gift_card_name)
            
            self.assertEqual(flt(result, 2), 200.0)
            mock_gift_card.db_set.assert_not_called()  # Should not update

    def test_06_api_validate_gift_card(self):
        """Test validate_gift_card API function."""
        from eumaria.api.gift_card import validate_gift_card
        
        gift_card_name = "TEST-GC-VALIDATE"
        
        # Test successful validation
        with patch.object(frappe, 'get_doc') as mock_get_doc, \
             patch('eumaria.api.gift_card.sync_gift_card_remaining_amount') as mock_sync:
            
            mock_gift_card = self._create_mock_gift_card(
                name=gift_card_name,
                disabled=0,
                docstatus=1,
                ends_on=add_days(getdate(), 30),
                starts_on=getdate(),
                mode_of_payment="Test Mode"
            )
            
            mock_get_doc.return_value = mock_gift_card
            mock_sync.return_value = 200.0
            
            result = validate_gift_card(gift_card_name, 150.0)
            
            self.assertTrue(result["valid"])
            self.assertIn("successfully", result["message"])
            self.assertEqual(flt(result["remaining_amount"], 2), 200.0)
            self.assertEqual(result["mode_of_payment"], "Test Mode")
        
        # Test disabled gift card
        with patch.object(frappe, 'get_doc') as mock_get_doc:
            mock_gift_card = self._create_mock_gift_card(disabled=1)
            mock_get_doc.return_value = mock_gift_card
            
            result = validate_gift_card(gift_card_name, 150.0)
            self.assertFalse(result["valid"])
            self.assertIn("disabled", result["message"])
        
        # Test expired gift card
        with patch.object(frappe, 'get_doc') as mock_get_doc:
            mock_gift_card = self._create_mock_gift_card(
                disabled=0,
                docstatus=1,
                ends_on=add_days(getdate(), -1)  # Past date
            )
            mock_get_doc.return_value = mock_gift_card
            
            result = validate_gift_card(gift_card_name, 150.0)
            self.assertFalse(result["valid"])
            self.assertIn("expired", result["message"])
        
        # Test insufficient balance
        with patch.object(frappe, 'get_doc') as mock_get_doc, \
             patch('eumaria.api.gift_card.sync_gift_card_remaining_amount') as mock_sync:
            
            mock_gift_card = self._create_mock_gift_card(
                disabled=0,
                docstatus=1,
                ends_on=add_days(getdate(), 30),
                starts_on=getdate()
            )
            
            mock_get_doc.return_value = mock_gift_card
            mock_sync.return_value = 50.0  # Only 50 available
            
            result = validate_gift_card(gift_card_name, 150.0)
            self.assertFalse(result["valid"])
            self.assertIn("Insufficient balance", result["message"])

    def test_07_api_get_gift_cards_for_customer(self):
        """Test get_gift_cards_for_customer API function."""
        from eumaria.api.gift_card import get_gift_cards_for_customer
        
        customer = "Test Customer"
        
        with patch.object(frappe, 'get_all') as mock_get_all, \
             patch('eumaria.api.gift_card.get_available_gift_card_amount') as mock_get_available, \
             patch.object(frappe.db, 'set_value') as mock_set_value:
            
            # Mock gift cards returned by get_all
            mock_gift_cards = [
                {
                    "name": "TEST-GC-1",
                    "remaining_amount": 100.0,
                    "ends_on": add_days(getdate(), 30),
                    "initial_amount": 100.0,
                    "mode_of_payment": "Test Mode",
                    "payment_entry": "TEST-PE-1"
                },
                {
                    "name": "TEST-GC-2",
                    "remaining_amount": 0.0,  # Zero balance
                    "ends_on": add_days(getdate(), 60),
                    "initial_amount": 200.0,
                    "mode_of_payment": "Test Mode",
                    "payment_entry": "TEST-PE-2"
                }
            ]
            
            mock_get_all.return_value = mock_gift_cards
            
            # Mock get_available_gift_card_amount
            def get_available_side_effect(card_dict):
                if card_dict["name"] == "TEST-GC-1":
                    return 80.0  # Different from remaining_amount
                else:
                    return 0.0  # Zero balance
            
            mock_get_available.side_effect = get_available_side_effect
            
            result = get_gift_cards_for_customer(customer)
            
            # Should return only cards with positive balance
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["name"], "TEST-GC-1")
            self.assertEqual(flt(result[0]["remaining_amount"], 2), 80.0)
            
            # Verify set_value was called to update remaining_amount
            mock_set_value.assert_called_once_with(
                "Eumaria Gift Card", "TEST-GC-1", "remaining_amount", 80.0
            )

    def test_08_api_allocate_gift_card(self):
        """Test allocate_gift_card API function."""
        from eumaria.api.gift_card import allocate_gift_card
        
        gift_card_name = "TEST-GC-ALLOCATE"
        
        # Test successful allocation
        with patch('eumaria.api.gift_card.validate_gift_card') as mock_validate, \
             patch('eumaria.api.gift_card.sync_gift_card_remaining_amount') as mock_sync:
            
            mock_validate.return_value = {"valid": True, "message": "Valid"}
            mock_sync.return_value = 200.0
            
            result = allocate_gift_card(gift_card_name, 150.0)
            
            self.assertTrue(result["success"])
            self.assertIn("synced successfully", result["message"])
            self.assertEqual(flt(result["new_balance"], 2), 200.0)
        
        # Test failed validation
        with patch('eumaria.api.gift_card.validate_gift_card') as mock_validate:
            mock_validate.return_value = {
                "valid": False,
                "message": "Gift card has expired"
            }
            
            result = allocate_gift_card(gift_card_name, 150.0)
            
            self.assertFalse(result["success"])
            self.assertEqual(result["message"], "Gift card has expired")
        
        # Test negative amount
        result = allocate_gift_card(gift_card_name, -50.0)
        self.assertFalse(result["success"])
        self.assertIn("cannot be negative", result["message"])

    def test_09_api_restore_gift_card(self):
        """Test restore_gift_card API function."""
        from eumaria.api.gift_card import restore_gift_card
        
        gift_card_name = "TEST-GC-RESTORE"
        
        with patch('eumaria.api.gift_card.sync_gift_card_remaining_amount') as mock_sync:
            mock_sync.return_value = 300.0
            
            result = restore_gift_card(gift_card_name, 100.0)
            
            self.assertTrue(result["success"])
            self.assertIn("restored successfully", result["message"])
            self.assertEqual(flt(result["new_balance"], 2), 300.0)

    def test_10_api_get_gift_card_balance(self):
        """Test get_gift_card_balance API function."""
        from eumaria.api.gift_card import get_gift_card_balance
        
        gift_card_name = "TEST-GC-BALANCE"
        
        # Test successful balance retrieval
        with patch.object(frappe, 'get_doc') as mock_get_doc, \
             patch('eumaria.api.gift_card.sync_gift_card_remaining_amount') as mock_sync, \
             patch('frappe.defaults.get_global_default') as mock_get_default:
            
            mock_gift_card = self._create_mock_gift_card(
                name=gift_card_name,
                docstatus=1,
                disabled=0,
                ends_on=add_days(getdate(), 30),
                starts_on=getdate()
            )
            
            mock_get_doc.return_value = mock_gift_card
            mock_sync.return_value = 250.0
            mock_get_default.return_value = "USD"
            
            result = get_gift_card_balance(gift_card_name)
            
            self.assertTrue(result["success"])
            self.assertEqual(flt(result["balance"], 2), 250.0)
            self.assertEqual(result["currency"], "USD")
            self.assertEqual(result["valid_until"], mock_gift_card.ends_on)
            self.assertTrue(result["is_valid"])
        
        # Test expired gift card
        with patch.object(frappe, 'get_doc') as mock_get_doc, \
             patch('eumaria.api.gift_card.sync_gift_card_remaining_amount') as mock_sync:
            
            mock_gift_card = self._create_mock_gift_card(
                name=gift_card_name,
                docstatus=1,
                disabled=0,
                ends_on=add_days(getdate(), -1),  # Expired
                starts_on=add_days(getdate(), -60)
            )
            
            mock_get_doc.return_value = mock_gift_card
            mock_sync.return_value = 100.0
            
            result = get_gift_card_balance(gift_card_name)
            
            self.assertTrue(result["success"])
            self.assertEqual(flt(result["balance"], 2), 100.0)
            self.assertFalse(result["is_valid"])  # Should be False due to expired date
        
        # Test non-existent gift card
        with patch.object(frappe, 'get_doc') as mock_get_doc:
            mock_get_doc.side_effect = frappe.DoesNotExistError
            
            result = get_gift_card_balance("NON-EXISTENT-GC")
            
            self.assertFalse(result["success"])
            self.assertIn("not found", result["message"])

    def test_11_create_gift_card_sales_invoice(self):
        """Test create_gift_card_sales_invoice function."""
        from eumaria.api.gift_card import create_gift_card_sales_invoice
        
        # Create mock appointment
        mock_appointment = MagicMock()
        mock_appointment.name = "TEST-APP-001"
        mock_appointment.patient = "Test Patient"
        mock_appointment.company = "Test Company"
        mock_appointment.paid_amount = 300.0
        
        # Create mock gift card
        mock_gift_card = self._create_mock_gift_card(
            name="TEST-GC-001",
            payment_entry="TEST-PE-001"
        )
        
        # Create mock sales invoice
        mock_sales_invoice = MagicMock()
        mock_sales_invoice.name = "TEST-SI-001"
        mock_sales_invoice.patient = "Test Patient"
        mock_sales_invoice.customer = "Test Customer"
        mock_sales_invoice.appointment = "TEST-APP-001"
        mock_sales_invoice.company = "Test Company"
        mock_sales_invoice.due_date = getdate()
        mock_sales_invoice.debit_to = "Debtors - TC"
        mock_sales_invoice.items = []
        mock_sales_invoice.advances = []
        mock_sales_invoice.additional_discount_percentage = 0.0
        mock_sales_invoice.discount_amount = 0.0
        mock_sales_invoice.allocate_advances_automatically = 0
        mock_sales_invoice.set_missing_values = MagicMock()
        mock_sales_invoice.calculate_taxes_and_totals = MagicMock()
        mock_sales_invoice.set_advances = MagicMock()
        mock_sales_invoice.append = MagicMock(side_effect=lambda doctype, args: args)
        mock_sales_invoice.save = MagicMock()
        mock_sales_invoice.submit = MagicMock()
        mock_sales_invoice.flags = MagicMock()
        
        with patch.object(frappe, 'new_doc') as mock_new_doc, \
             patch.object(frappe, 'get_value') as mock_get_value, \
             patch('healthcare.healthcare.doctype.healthcare_settings.healthcare_settings.get_receivable_account') as mock_get_receivable_account, \
             patch('healthcare.healthcare.doctype.patient_appointment.patient_appointment.get_appointment_item') as mock_get_appointment_item:
            
            mock_new_doc.return_value = mock_sales_invoice
            mock_get_value.return_value = "Test Customer"
            mock_get_receivable_account.return_value = "Debtors - TC"
            mock_get_appointment_item.return_value = {"item_code": "Test Item"}
            
            # Mock advances with matching payment entry
            mock_advance = MagicMock()
            mock_advance.reference_type = "Payment Entry"
            mock_advance.reference_name = "TEST-PE-001"
            mock_advance.advance_amount = 500.0
            mock_advance.reference_row = "row1"
            mock_advance.remarks = "Test"
            mock_advance.ref_exchange_rate = 1.0
            
            mock_sales_invoice.advances = [mock_advance]
            
            # Test successful invoice creation
            sales_invoice, allocated_amount = create_gift_card_sales_invoice(
                mock_appointment,
                mock_gift_card
            )
            
            self.assertEqual(sales_invoice.name, "TEST-SI-001")
            self.assertEqual(flt(allocated_amount, 2), 300.0)
            mock_sales_invoice.save.assert_called_once_with(ignore_permissions=True)
            mock_sales_invoice.submit.assert_called_once()
            
            # Test with discount
            mock_sales_invoice.reset_mock()
            sales_invoice, allocated_amount = create_gift_card_sales_invoice(
                mock_appointment,
                mock_gift_card,
                discount_percentage=10.0
            )
            
            self.assertEqual(flt(mock_sales_invoice.additional_discount_percentage, 2), 10.0)
            
            # Test insufficient balance
            mock_advance.advance_amount = 200.0  # Less than paid_amount
            with self.assertRaises(frappe.ValidationError) as cm:
                create_gift_card_sales_invoice(mock_appointment, mock_gift_card)
            
            self.assertIn("Insufficient gift card balance", str(cm.exception))
            
            # Test no matching advance
            mock_advance.reference_name = "DIFFERENT-PE"  # Not matching gift card payment entry
            with self.assertRaises(frappe.ValidationError) as cm:
                create_gift_card_sales_invoice(mock_appointment, mock_gift_card)
            
            self.assertIn("No available advance", str(cm.exception))

    def test_12_invoice_appointment_with_gift_card(self):
        """Test invoice_appointment_with_gift_card API function."""
        from eumaria.api.gift_card import invoice_appointment_with_gift_card
        
        appointment_name = "TEST-APP-001"
        gift_card_name = "TEST-GC-001"
        
        # Create mock appointment
        mock_appointment = MagicMock()
        mock_appointment.name = appointment_name
        mock_appointment.patient = "Test Patient"
        mock_appointment.appointment_date = getdate()
        mock_appointment.paid_amount = 300.0
        mock_appointment.mode_of_payment = None
        mock_appointment.invoiced = 0
        mock_appointment.selected_gift_card = None
        mock_appointment.db_set = MagicMock()
        mock_appointment.notify_update = MagicMock()
        
        # Create mock gift card
        mock_gift_card = self._create_mock_gift_card(
            name=gift_card_name,
            payment_entry="TEST-PE-001"
        )
        
        # Create mock sales invoice
        mock_sales_invoice = MagicMock()
        mock_sales_invoice.name = "TEST-SI-001"
        
        with patch.object(frappe, 'get_doc') as mock_get_doc, \
             patch('eumaria.api.gift_card.validate_gift_card') as mock_validate, \
             patch('eumaria.api.gift_card.create_gift_card_sales_invoice') as mock_create_invoice, \
             patch('eumaria.api.gift_card.sync_gift_card_remaining_amount') as mock_sync, \
             patch('frappe.get_single') as mock_get_single, \
             patch('healthcare.healthcare.doctype.fee_validity.fee_validity.check_fee_validity') as mock_check_fee_validity, \
             patch('healthcare.healthcare.doctype.fee_validity.fee_validity.get_fee_validity') as mock_get_fee_validity, \
             patch('healthcare.healthcare.doctype.patient_appointment.patient_appointment.update_fee_validity') as mock_update_fee_validity:
            
            mock_get_doc.side_effect = [mock_appointment, mock_gift_card]
            mock_validate.return_value = {"valid": True, "message": "Valid"}
            mock_create_invoice.return_value = (mock_sales_invoice, 300.0)
            mock_sync.return_value = 200.0
            
            # Mock healthcare settings
            mock_settings = MagicMock()
            mock_settings.show_payment_popup = 1
            mock_settings.enable_free_follow_ups = 0
            mock_get_single.return_value = mock_settings
            
            # Mock fee validity
            mock_check_fee_validity.return_value = None
            mock_get_fee_validity.return_value = None
            
            # Test successful invoice creation
            result = invoice_appointment_with_gift_card(
                appointment_name=appointment_name,
                gift_card=gift_card_name
            )
            
            self.assertTrue(result["success"])
            self.assertEqual(result["sales_invoice"], "TEST-SI-001")
            self.assertEqual(result["payment_entry"], "TEST-PE-001")
            
            # Verify appointment was updated
            mock_appointment.db_set.assert_called()
            self.assertEqual(mock_appointment.db_set.call_args[0][0]["invoiced"], 1)
            self.assertEqual(mock_appointment.db_set.call_args[0][0]["ref_sales_invoice"], "TEST-SI-001")
            self.assertEqual(mock_appointment.db_set.call_args[0][0]["use_gift_card"], 1)
            self.assertEqual(mock_appointment.db_set.call_args[0][0]["selected_gift_card"], gift_card_name)
            self.assertEqual(flt(mock_appointment.db_set.call_args[0][0]["gift_card_allocated_amount"], 2), 300.0)
            
            # Test with appointment already having mode_of_payment
            mock_appointment.mode_of_payment = "Cash"
            result = invoice_appointment_with_gift_card(
                appointment_name=appointment_name,
                gift_card=gift_card_name
            )
            
            self.assertFalse(result["success"])
            self.assertIn("Cannot use both gift card and regular payment method", result["message"])
            
            # Test with already invoiced appointment
            mock_appointment.mode_of_payment = None
            mock_appointment.invoiced = 1
            result = invoice_appointment_with_gift_card(
                appointment_name=appointment_name,
                gift_card=gift_card_name
            )
            
            self.assertFalse(result["success"])
            self.assertIn("Invoice cannot be created", result["message"])
            
            # Test with fee validity
            mock_appointment.invoiced = 0
            mock_check_fee_validity.return_value = MagicMock(status="Active")
            result = invoice_appointment_with_gift_card(
                appointment_name=appointment_name,
                gift_card=gift_card_name
            )
            
            # Should still create invoice since fee validity is active
            self.assertTrue(result["success"])
            
            # Test with existing fee validity
            mock_check_fee_validity.return_value = None
            mock_get_fee_validity.return_value = MagicMock()  # Existing fee validity
            result = invoice_appointment_with_gift_card(
                appointment_name=appointment_name,
                gift_card=gift_card_name
            )
            
            self.assertTrue(result["success"])
            self.assertIn("Fee validity exists", result["message"])

    def test_13_on_sales_invoice_cancel_hook(self):
        """Test on_sales_invoice_cancel hook function."""
        from eumaria.overrides.invoice_creation import on_sales_invoice_cancel
        
        # Create mock sales invoice with appointment item
        mock_sales_invoice = MagicMock()
        mock_sales_invoice.items = [
            MagicMock(reference_dt="Patient Appointment", reference_dn="TEST-APP-001")
        ]
        
        # Create mock appointment
        mock_appointment = MagicMock()
        mock_appointment.name = "TEST-APP-001"
        mock_appointment.use_gift_card = 1
        mock_appointment.selected_gift_card = "TEST-GC-001"
        mock_appointment.db_set = MagicMock()
        
        with patch.object(frappe, 'get_doc') as mock_get_doc, \
             patch('eumaria.api.gift_card.sync_gift_card_remaining_amount') as mock_sync:
            
            mock_get_doc.return_value = mock_appointment
            
            # Test cancellation with gift card
            on_sales_invoice_cancel(mock_sales_invoice, "on_cancel")
            
            # Verify gift card was synced and appointment fields cleared
            mock_sync.assert_called_once_with("TEST-GC-001")
            mock_appointment.db_set.assert_called_once_with({
                "gift_card_allocated_amount": 0,
                "selected_gift_card": "",
                "use_gift_card": 0,
            })
            
            # Test cancellation without gift card
            mock_appointment.use_gift_card = 0
            mock_sync.reset_mock()
            mock_appointment.db_set.reset_mock()
            
            on_sales_invoice_cancel(mock_sales_invoice, "on_cancel")
            
            # Should not sync or clear fields
            mock_sync.assert_not_called()
            mock_appointment.db_set.assert_not_called()