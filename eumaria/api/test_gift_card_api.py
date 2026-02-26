# Copyright (c) 2026, KAINOTOMO PH LTD and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.tests import FrappeTestCase
from frappe.utils import getdate, nowdate, add_days, flt
import unittest
from unittest.mock import patch, MagicMock


class TestGiftCardAPI(FrappeTestCase):
    """Unit tests for gift card API functions."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        
        # Create test customer
        if not frappe.db.exists("Customer", "Test Customer API"):
            customer = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": "Test Customer API",
                "customer_type": "Individual",
                "customer_group": "All Customer Groups",
                "territory": "All Territories"
            })
            customer.insert(ignore_permissions=True)
        
        # Create test patient linked to customer
        if not frappe.db.exists("Patient", "Test Patient API"):
            patient = frappe.get_doc({
                "doctype": "Patient",
                "first_name": "Test",
                "last_name": "Patient API",
                "sex": "Female",
                "customer": "Test Customer API"
            })
            patient.insert(ignore_permissions=True)
        
        frappe.db.commit()

    def tearDown(self):
        """Clean up after each test."""
        frappe.db.rollback()
        super().tearDown()

    def test_get_available_gift_card_amount(self):
        """Test get_available_gift_card_amount function."""
        from eumaria.api.gift_card import get_available_gift_card_amount
        
        # Create mock gift card document
        mock_gift_card = frappe._dict({
            "payment_entry": "TEST-PE-001",
            "remaining_amount": 150.0
        })
        
        # Test with payment entry
        with patch.object(frappe.db, 'get_value') as mock_get_value:
            mock_get_value.return_value = (100.0, 1)  # unallocated_amount, docstatus
            amount = get_available_gift_card_amount(mock_gift_card)
            self.assertEqual(flt(amount, 2), 100.0)
        
        # Test without payment entry
        mock_gift_card_no_pe = frappe._dict({
            "payment_entry": None,
            "remaining_amount": 150.0
        })
        amount = get_available_gift_card_amount(mock_gift_card_no_pe)
        self.assertEqual(flt(amount, 2), 150.0)
        
        # Test with payment entry but not submitted
        with patch.object(frappe.db, 'get_value') as mock_get_value:
            mock_get_value.return_value = (100.0, 0)  # docstatus = 0 (draft)
            amount = get_available_gift_card_amount(mock_gift_card)
            self.assertEqual(flt(amount, 2), 0.0)
        
        # Test with payment entry cancelled
        with patch.object(frappe.db, 'get_value') as mock_get_value:
            mock_get_value.return_value = (100.0, 2)  # docstatus = 2 (cancelled)
            amount = get_available_gift_card_amount(mock_gift_card)
            self.assertEqual(flt(amount, 2), 0.0)

    def test_sync_gift_card_remaining_amount(self):
        """Test sync_gift_card_remaining_amount function."""
        from eumaria.api.gift_card import sync_gift_card_remaining_amount
        
        # Create mock gift card
        gift_card_name = "TEST-GC-001"
        
        # Mock frappe.get_doc to return a mock gift card
        mock_gift_card = MagicMock()
        mock_gift_card.name = gift_card_name
        mock_gift_card.remaining_amount = 200.0
        
        with patch.object(frappe, 'get_doc') as mock_get_doc, \
             patch('eumaria.api.gift_card.get_available_gift_card_amount') as mock_get_available:
            
            mock_get_doc.return_value = mock_gift_card
            mock_get_available.return_value = 150.0
            
            # Test when amounts differ
            result = sync_gift_card_remaining_amount(gift_card_name)
            
            # Should update remaining_amount
            mock_gift_card.db_set.assert_called_once_with("remaining_amount", 150.0)
            self.assertEqual(flt(result, 2), 150.0)
        
        # Test when amounts are equal
        with patch.object(frappe, 'get_doc') as mock_get_doc, \
             patch('eumaria.api.gift_card.get_available_gift_card_amount') as mock_get_available:
            
            mock_gift_card = MagicMock()
            mock_gift_card.name = gift_card_name
            mock_gift_card.remaining_amount = 150.0
            
            mock_get_doc.return_value = mock_gift_card
            mock_get_available.return_value = 150.0
            
            result = sync_gift_card_remaining_amount(gift_card_name)
            
            # Should not update since amounts are equal
            mock_gift_card.db_set.assert_not_called()
            self.assertEqual(flt(result, 2), 150.0)

    def test_validate_gift_card_success(self):
        """Test validate_gift_card function with successful validation."""
        from eumaria.api.gift_card import validate_gift_card
        
        gift_card_name = "TEST-GC-VALID"
        
        # Create mock gift card document
        mock_gift_card = MagicMock()
        mock_gift_card.name = gift_card_name
        mock_gift_card.disabled = 0
        mock_gift_card.docstatus = 1
        mock_gift_card.ends_on = add_days(getdate(), 30)
        mock_gift_card.starts_on = getdate()
        mock_gift_card.mode_of_payment = "Test Mode"
        
        with patch.object(frappe, 'get_doc') as mock_get_doc, \
             patch('eumaria.api.gift_card.sync_gift_card_remaining_amount') as mock_sync:
            
            mock_get_doc.return_value = mock_gift_card
            mock_sync.return_value = 200.0
            
            result = validate_gift_card(gift_card_name, 150.0)
            
            self.assertTrue(result["valid"])
            self.assertIn("successfully", result["message"])
            self.assertEqual(flt(result["remaining_amount"], 2), 200.0)
            self.assertEqual(result["mode_of_payment"], "Test Mode")

    def test_validate_gift_card_disabled(self):
        """Test validate_gift_card with disabled gift card."""
        from eumaria.api.gift_card import validate_gift_card
        
        gift_card_name = "TEST-GC-DISABLED"
        
        mock_gift_card = MagicMock()
        mock_gift_card.disabled = 1
        
        with patch.object(frappe, 'get_doc') as mock_get_doc:
            mock_get_doc.return_value = mock_gift_card
            
            result = validate_gift_card(gift_card_name, 100.0)
            
            self.assertFalse(result["valid"])
            self.assertIn("disabled", result["message"])

    def test_validate_gift_card_not_submitted(self):
        """Test validate_gift_card with non-submitted gift card."""
        from eumaria.api.gift_card import validate_gift_card
        
        gift_card_name = "TEST-GC-DRAFT"
        
        mock_gift_card = MagicMock()
        mock_gift_card.disabled = 0
        mock_gift_card.docstatus = 0  # Draft
        
        with patch.object(frappe, 'get_doc') as mock_get_doc:
            mock_get_doc.return_value = mock_gift_card
            
            result = validate_gift_card(gift_card_name, 100.0)
            
            self.assertFalse(result["valid"])
            self.assertIn("not submitted", result["message"])

    def test_validate_gift_card_expired(self):
        """Test validate_gift_card with expired gift card."""
        from eumaria.api.gift_card import validate_gift_card
        
        gift_card_name = "TEST-GC-EXPIRED"
        
        mock_gift_card = MagicMock()
        mock_gift_card.disabled = 0
        mock_gift_card.docstatus = 1
        mock_gift_card.ends_on = add_days(getdate(), -1)  # Past date
        mock_gift_card.starts_on = add_days(getdate(), -60)
        
        with patch.object(frappe, 'get_doc') as mock_get_doc:
            mock_get_doc.return_value = mock_gift_card
            
            result = validate_gift_card(gift_card_name, 100.0)
            
            self.assertFalse(result["valid"])
            self.assertIn("expired", result["message"])

    def test_validate_gift_card_not_yet_valid(self):
        """Test validate_gift_card with gift card that hasn't started yet."""
        from eumaria.api.gift_card import validate_gift_card
        
        gift_card_name = "TEST-GC-FUTURE"
        
        mock_gift_card = MagicMock()
        mock_gift_card.disabled = 0
        mock_gift_card.docstatus = 1
        mock_gift_card.ends_on = add_days(getdate(), 60)
        mock_gift_card.starts_on = add_days(getdate(), 5)  # Future start date
        
        with patch.object(frappe, 'get_doc') as mock_get_doc:
            mock_get_doc.return_value = mock_gift_card
            
            result = validate_gift_card(gift_card_name, 100.0)
            
            self.assertFalse(result["valid"])
            self.assertIn("not yet valid", result["message"])

    def test_validate_gift_card_insufficient_balance(self):
        """Test validate_gift_card with insufficient balance."""
        from eumaria.api.gift_card import validate_gift_card
        
        gift_card_name = "TEST-GC-LOW-BALANCE"
        
        mock_gift_card = MagicMock()
        mock_gift_card.disabled = 0
        mock_gift_card.docstatus = 1
        mock_gift_card.ends_on = add_days(getdate(), 30)
        mock_gift_card.starts_on = getdate()
        
        with patch.object(frappe, 'get_doc') as mock_get_doc, \
             patch('eumaria.api.gift_card.sync_gift_card_remaining_amount') as mock_sync:
            
            mock_get_doc.return_value = mock_gift_card
            mock_sync.return_value = 50.0  # Only 50 available
            
            result = validate_gift_card(gift_card_name, 100.0)
            
            self.assertFalse(result["valid"])
            self.assertIn("Insufficient balance", result["message"])
            self.assertIn("50", result["message"])
            self.assertIn("100", result["message"])

    def test_validate_gift_card_skip_balance_check(self):
        """Test validate_gift_card with skip_balance_check=True."""
        from eumaria.api.gift_card import validate_gift_card
        
        gift_card_name = "TEST-GC-SKIP-BALANCE"
        
        mock_gift_card = MagicMock()
        mock_gift_card.disabled = 0
        mock_gift_card.docstatus = 1
        mock_gift_card.ends_on = add_days(getdate(), 30)
        mock_gift_card.starts_on = getdate()
        
        with patch.object(frappe, 'get_doc') as mock_get_doc, \
             patch('eumaria.api.gift_card.sync_gift_card_remaining_amount') as mock_sync:
            
            mock_get_doc.return_value = mock_gift_card
            mock_sync.return_value = 50.0  # Only 50 available
            
            # Should pass even with insufficient balance when skip_balance_check=True
            result = validate_gift_card(gift_card_name, 100.0, skip_balance_check=True)
            
            self.assertTrue(result["valid"])
            self.assertIn("successfully", result["message"])

    def test_validate_gift_card_not_found(self):
        """Test validate_gift_card with non-existent gift card."""
        from eumaria.api.gift_card import validate_gift_card
        
        gift_card_name = "NON-EXISTENT-GC"
        
        with patch.object(frappe, 'get_doc') as mock_get_doc:
            mock_get_doc.side_effect = frappe.DoesNotExistError
            
            result = validate_gift_card(gift_card_name, 100.0)
            
            self.assertFalse(result["valid"])
            self.assertIn("not found", result["message"])

    def test_get_gift_cards_for_customer(self):
        """Test get_gift_cards_for_customer function."""
        from eumaria.api.gift_card import get_gift_cards_for_customer
        
        customer = "Test Customer API"
        
        # Mock frappe.get_all to return test gift cards
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
                "remaining_amount": 200.0,
                "ends_on": add_days(getdate(), 60),
                "initial_amount": 200.0,
                "mode_of_payment": "Test Mode",
                "payment_entry": "TEST-PE-2"
            },
            {
                "name": "TEST-GC-EXPIRED",
                "remaining_amount": 50.0,
                "ends_on": add_days(getdate(), -1),  # Expired
                "initial_amount": 50.0,
                "mode_of_payment": "Test Mode",
                "payment_entry": "TEST-PE-3"
            }
        ]
        
        with patch.object(frappe, 'get_all') as mock_get_all, \
             patch('eumaria.api.gift_card.get_available_gift_card_amount') as mock_get_available, \
             patch.object(frappe.db, 'set_value') as mock_set_value:
            
            mock_get_all.return_value = mock_gift_cards
            
            # Mock get_available_gift_card_amount to return different amounts
            def get_available_side_effect(card_dict):
                if card_dict["name"] == "TEST-GC-1":
                    return 80.0  # Different from remaining_amount
                elif card_dict["name"] == "TEST-GC-2":
                    return 200.0  # Same as remaining_amount
                else:
                    return 0.0  # Zero balance
            
            mock_get_available.side_effect = get_available_side_effect
            
            result = get_gift_cards_for_customer(customer)
            
            # Should return only non-expired cards with positive balance
            self.assertEqual(len(result), 2)
            
            # TEST-GC-1 should have remaining_amount updated
            card1 = next(c for c in result if c["name"] == "TEST-GC-1")
            self.assertEqual(flt(card1["remaining_amount"], 2), 80.0)
            
            # TEST-GC-2 should have same remaining_amount
            card2 = next(c for c in result if c["name"] == "TEST-GC-2")
            self.assertEqual(flt(card2["remaining_amount"], 2), 200.0)
            
            # TEST-GC-EXPIRED should not be in result
            expired_cards = [c for c in result if c["name"] == "TEST-GC-EXPIRED"]
            self.assertEqual(len(expired_cards), 0)
            
            # Verify set_value was called for TEST-GC-1 (amounts differed)
            mock_set_value.assert_called_once_with(
                "Eumaria Gift Card", "TEST-GC-1", "remaining_amount", 80.0
            )

    def test_get_gift_cards_for_customer_empty(self):
        """Test get_gift_cards_for_customer with empty customer."""
        from eumaria.api.gift_card import get_gift_cards_for_customer
        
        result = get_gift_cards_for_customer("")
        self.assertEqual(result, [])
        
        result = get_gift_cards_for_customer(None)
        self.assertEqual(result, [])

    def test_allocate_gift_card_success(self):
        """Test allocate_gift_card function with successful allocation."""
        from eumaria.api.gift_card import allocate_gift_card
        
        gift_card_name = "TEST-GC-ALLOCATE"
        amount = 150.0
        
        with patch('eumaria.api.gift_card.validate_gift_card') as mock_validate, \
             patch('eumaria.api.gift_card.sync_gift_card_remaining_amount') as mock_sync:
            
            mock_validate.return_value = {"valid": True, "message": "Valid"}
            mock_sync.return_value = 200.0
            
            result = allocate_gift_card(gift_card_name, amount)
            
            self.assertTrue(result["success"])
            self.assertIn("synced successfully", result["message"])
            self.assertEqual(flt(result["new_balance"], 2), 200.0)

    def test_allocate_gift_card_validation_failed(self):
        """Test allocate_gift_card with failed validation."""
        from eumaria.api.gift_card import allocate_gift_card
        
        gift_card_name = "TEST-GC-INVALID"
        amount = 150.0
        
        with patch('eumaria.api.gift_card.validate_gift_card') as mock_validate:
            mock_validate.return_value = {
                "valid": False,
                "message": "Gift card has expired"
            }
            
            result = allocate_gift_card(gift_card_name, amount)
            
            self.assertFalse(result["success"])
            self.assertEqual(result["message"], "Gift card has expired")

    def test_allocate_gift_card_negative_amount(self):
        """Test allocate_gift_card with negative amount."""
        from eumaria.api.gift_card import allocate_gift_card
        
        result = allocate_gift_card("TEST-GC", -50.0)
        
        self.assertFalse(result["success"])
        self.assertIn("cannot be negative", result["message"])

    def test_restore_gift_card(self):
        """Test restore_gift_card function."""
        from eumaria.api.gift_card import restore_gift_card
        
        gift_card_name = "TEST-GC-RESTORE"
        
        with patch('eumaria.api.gift_card.sync_gift_card_remaining_amount') as mock_sync:
            mock_sync.return_value = 300.0
            
            result = restore_gift_card(gift_card_name, 100.0)
            
            self.assertTrue(result["success"])
            self.assertIn("restored successfully", result["message"])
            self.assertEqual(flt(result["new_balance"], 2), 300.0)

    def test_get_gift_card_balance_success(self):
        """Test get_gift_card_balance function with valid gift card."""
        from eumaria.api.gift_card import get_gift_card_balance
        
        gift_card_name = "TEST-GC-BALANCE"
        
        # Create mock gift card
        mock_gift_card = MagicMock()
        mock_gift_card.name = gift_card_name
        mock_gift_card.docstatus = 1
        mock_gift_card.disabled = 0
        mock_gift_card.ends_on = add_days(getdate(), 30)
        mock_gift_card.starts_on = getdate()
        
        with patch.object(frappe, 'get_doc') as mock_get_doc, \
             patch('eumaria.api.gift_card.sync_gift_card_remaining_amount') as mock_sync, \
             patch('frappe.defaults.get_global_default') as mock_get_default:
            
            mock_get_doc.return_value = mock_gift_card
            mock_sync.return_value = 250.0
            mock_get_default.return_value = "USD"
            
            result = get_gift_card_balance(gift_card_name)
            
            self.assertTrue(result["success"])
            self.assertEqual(flt(result["balance"], 2), 250.0)
            self.assertEqual(result["currency"], "USD")
            self.assertEqual(result["valid_until"], mock_gift_card.ends_on)
            self.assertTrue(result["is_valid"])

    def test_get_gift_card_balance_not_found(self):
        """Test get_gift_card_balance with non-existent gift card."""
        from eumaria.api.gift_card import get_gift_card_balance
        
        with patch.object(frappe, 'get_doc') as mock_get_doc:
            mock_get_doc.side_effect = frappe.DoesNotExistError
            
            result = get_gift_card_balance("NON-EXISTENT-GC")
            
            self.assertFalse(result["success"])
            self.assertIn("not found", result["message"])

    def test_get_gift_card_balance_invalid(self):
        """Test get_gift_card_balance with invalid gift card."""
        from eumaria.api.gift_card import get_gift_card_balance
        
        gift_card_name = "TEST-GC-INVALID"
        
        # Create mock expired gift card
        mock_gift_card = MagicMock()
        mock_gift_card.name = gift_card_name
        mock_gift_card.docstatus = 1
        mock_gift_card.disabled = 0
        mock_gift_card.ends_on = add_days(getdate(), -1)  # Expired
        mock_gift_card.starts_on = add_days(getdate(), -60)
        
        with patch.object(frappe, 'get_doc') as mock_get_doc, \
             patch('eumaria.api.gift_card.sync_gift_card_remaining_amount') as mock_sync:
            
            mock_get_doc.return_value = mock_gift_card
            mock_sync.return_value = 100.0
            
            result = get_gift_card_balance(gift_card_name)
            
            self.assertTrue(result["success"])
            self.assertEqual(flt(result["balance"], 2), 100.0)
            self.assertFalse(result["is_valid"])  # Should be False due to expired date