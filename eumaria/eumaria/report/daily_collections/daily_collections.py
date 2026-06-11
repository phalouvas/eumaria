# Copyright (c) 2026, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate

PILATES_ITEM_CODES = [
	"CLINICAL PILATES GROUP",
	"CLINICAL PILATES GROUP New",
	"PRIVATE CLINICAL PILATES",
]


def execute(filters=None):
	"""Return daily collections aggregated by Mode of Payment, excluding Pilates invoices."""

	if not filters:
		filters = frappe._dict({})

	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns():
	return [
		{
			"fieldname": "mode_of_payment",
			"label": _("Mode of Payment"),
			"fieldtype": "Data",
			"width": 300,
		},
		{
			"fieldname": "amount",
			"label": _("Amount"),
			"fieldtype": "Currency",
			"width": 200,
		},
	]


def get_data(filters):
	"""Query Sales Invoice Payment totals grouped by mode_of_payment, excluding Pilates invoices."""

	from_date = getdate(filters.get("from_date"))
	to_date = getdate(filters.get("to_date"))

	data = frappe.db.sql(
		"""
		SELECT
			sip.mode_of_payment,
			SUM(sip.amount) AS amount
		FROM `tabSales Invoice Payment` sip
		INNER JOIN `tabSales Invoice` si ON si.name = sip.parent
		WHERE
			si.docstatus = 1
			AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND si.name NOT IN (
				SELECT DISTINCT sii.parent
				FROM `tabSales Invoice Item` sii
				WHERE sii.item_code IN %(pilates_codes)s
			)
		GROUP BY sip.mode_of_payment
		ORDER BY sip.mode_of_payment
		""",
		{
			"from_date": from_date,
			"to_date": to_date,
			"pilates_codes": PILATES_ITEM_CODES,
		},
		as_dict=True,
	)

	return data
