# Copyright (c) 2026, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.exceptions import DoesNotExistError
from frappe.model.document import Document
from frappe.utils import getdate, nowdate


class EumariaGiftCard(Document):
	"""
	Eumaria Gift Card doctype.

	- Sets remaining_amount equal to initial_amount on creation.
	- Creates a Payment Entry when a new gift card is saved.
	- Submits the linked Payment Entry when the gift card is submitted.
	- Cancels the linked Payment Entry when the gift card is cancelled.
	"""
	def validate(self):
		"""Validate the gift card.

		- For new gift cards, set remaining_amount equal to initial_amount.
		- If patient is set and customer is not, populate customer from the linked patient.
		- Ensure that patient is set, raising an error if it is missing.
		"""
		if self.is_new() and not self.get("amended_from"):
			self.remaining_amount = self.initial_amount
		
		# Populate customer from patient if patient is set
		if self.patient and not self.customer:
			try:
				# Get customer linked to the patient
				patient_customer = frappe.get_value("Patient", self.patient, "customer")
				if patient_customer:
					self.customer = patient_customer
				else:
					frappe.throw(_("Patient {0} is not linked to any customer. Please link the patient to a customer first.").format(self.patient))
			except Exception as e:
				frappe.log_error(
					title=_("Failed to fetch customer from patient {0}").format(self.patient),
					message=frappe.get_traceback(),
				)
				frappe.throw(_("Failed to get customer from patient: {0}").format(str(e)))
		
		# Also validate that patient is set (it's required in JSON but double-check)
		if not self.patient:
			frappe.throw(_("Patient is required"))

	def after_insert(self):
		"""Create a Payment Entry for the gift card."""
		if self.get("amended_from"):
			# Don't create payment entry for amended documents
			return

		# Validate required fields
		if not self.patient:
			frappe.throw(_("Patient is required to create payment entry"))
		if not self.customer:
			frappe.throw(_("Customer is required to create payment entry. Please ensure the patient is linked to a customer."))
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

			# Prepare payment entry data
			payment_entry_data = {
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
			}
			
			# Add reference_no and reference_date if provided by user
			if self.reference_no:
				payment_entry_data["reference_no"] = self.reference_no
			
			if self.reference_date:
				payment_entry_data["reference_date"] = self.reference_date
			
			# Create payment entry
			payment_entry = frappe.get_doc(payment_entry_data)
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
