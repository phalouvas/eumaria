# Copyright (c) 2026, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.exceptions import DoesNotExistError
from frappe.model.document import Document
from frappe.utils import getdate


class EumariaGiftCard(Document):
	"""
	Eumaria Gift Card doctype.

	- Sets remaining_amount equal to initial_amount on creation.
	- Creates a Payment Entry when a new gift card is saved.
	- Submits the linked Payment Entry when the gift card is submitted.
	- Cancels the linked Payment Entry when the gift card is cancelled.
	"""
	def validate(self):
		"""Set remaining_amount equal to initial_amount for new gift cards."""
		if self.is_new() and not self.get("amended_from"):
			self.remaining_amount = self.initial_amount

	def after_insert(self):
		"""Create a Payment Entry for the gift card."""
		if self.get("amended_from"):
			# Don't create payment entry for amended documents
			return

		# Validate required fields
		if not self.customer:
			frappe.throw(_("Customer is required to create payment entry"))
		if not self.mode_of_payment:
			frappe.throw(_("Mode of Payment is required to create payment entry"))
		if not self.initial_amount or self.initial_amount <= 0:
			frappe.throw(_("Initial Amount must be greater than 0"))

		company = frappe.defaults.get_defaults().company
		if not company:
			frappe.throw(_("Default company not set in system defaults"))

		try:
			# Get default account for mode of payment
			paid_to_account = frappe.get_value(
				"Mode of Payment Account",
				{"parent": self.mode_of_payment, "company": company},
				"default_account"
			)
			if not paid_to_account:
				frappe.throw(_("No default account found for Mode of Payment {0} and company {1}").format(
					self.mode_of_payment, company
				))

			# Create payment entry
			payment_entry = frappe.get_doc({
				"doctype": "Payment Entry",
				"payment_type": "Receive",
				"party_type": "Customer",
				"party": self.customer,
				"paid_amount": self.initial_amount,
				"received_amount": self.initial_amount,
				"mode_of_payment": self.mode_of_payment,
				"paid_to": paid_to_account,
				"reference_date": getdate(),
				"posting_date": getdate(),
				"company": company,
				"remarks": _("Gift card {0}").format(self.name),
			})
			payment_entry.insert(ignore_permissions=True)

			# Link payment entry to gift card
			self.db_set("payment_entry", payment_entry.name)

		except Exception as e:
			frappe.log_error(
				title=_("Payment Entry creation failed for Gift Card {0}").format(self.name),
				message=frappe.get_traceback(),
			)
			frappe.throw(_("Failed to create Payment Entry: {0}").format(str(e)))

	def on_submit(self):
		"""Submit the linked Payment Entry."""
		if not self.payment_entry:
			frappe.throw(_("Payment Entry is not linked. Cannot submit gift card."))

		try:
			payment_entry = frappe.get_doc("Payment Entry", self.payment_entry)
		except DoesNotExistError:
			frappe.throw(_("Linked Payment Entry {0} does not exist.").format(self.payment_entry))
		except Exception as e:
			frappe.log_error(
				title=_("Payment Entry fetch failed for Gift Card {0}").format(self.name),
				message=frappe.get_traceback(),
			)
			frappe.throw(_("Failed to fetch Payment Entry: {0}").format(str(e)))

		try:
			if payment_entry.docstatus == 0:
				payment_entry.submit()
			elif payment_entry.docstatus == 2:
				frappe.throw(_("Linked Payment Entry is cancelled. Cannot submit gift card."))
			# If already submitted (docstatus == 1), proceed silently
		except Exception as e:
			frappe.log_error(
				title=_("Payment Entry submission failed for Gift Card {0}").format(self.name),
				message=frappe.get_traceback(),
			)
			frappe.throw(_("Failed to submit Payment Entry: {0}").format(str(e)))

	def on_cancel(self):
		"""Cancel the linked Payment Entry."""
		if not self.payment_entry:
			return

		try:
			payment_entry = frappe.get_doc("Payment Entry", self.payment_entry)
		except DoesNotExistError:
			frappe.throw(_("Linked Payment Entry {0} does not exist.").format(self.payment_entry))
		except Exception as e:
			frappe.log_error(
				title=_("Payment Entry fetch failed for Gift Card {0}").format(self.name),
				message=frappe.get_traceback(),
			)
			frappe.throw(_("Failed to fetch Payment Entry: {0}").format(str(e)))

		try:
			if payment_entry.docstatus == 1:
				payment_entry.cancel()
			# If already cancelled (docstatus == 2) or draft, do nothing
		except Exception as e:
			frappe.log_error(
				title=_("Payment Entry cancellation failed for Gift Card {0}").format(self.name),
				message=frappe.get_traceback(),
			)
			frappe.throw(_("Failed to cancel Payment Entry: {0}").format(str(e)))
