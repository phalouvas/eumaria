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
	"""Return daily collections aggregated by Mode of Payment."""

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
	"""Query Sales Invoice Payment totals grouped by mode_of_payment.

	By default, include Pilates invoices; exclude them only when include_pilates is unchecked.
	"""

	from_date = getdate(filters.get("from_date"))
	to_date = getdate(filters.get("to_date"))
	include_pilates = filters.get("include_pilates")
	include_pilates = 1 if include_pilates in (None, "", "1", 1, True) else 0

	pilates_exclusion_clause = ""
	query_values = {
		"from_date": from_date,
		"to_date": to_date,
	}

	if not include_pilates:
		pilates_exclusion_clause = """
			AND si.name NOT IN (
				SELECT DISTINCT sii.parent
				FROM `tabSales Invoice Item` sii
				WHERE sii.item_code IN %(pilates_codes)s
			)
		"""
		query_values["pilates_codes"] = PILATES_ITEM_CODES

	data = frappe.db.sql(
		f"""
		SELECT
			sip.mode_of_payment,
			SUM(sip.amount) AS amount
		FROM `tabSales Invoice Payment` sip
		INNER JOIN `tabSales Invoice` si ON si.name = sip.parent
		WHERE
			si.docstatus = 1
			AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
			{pilates_exclusion_clause}
		GROUP BY sip.mode_of_payment
		ORDER BY sip.mode_of_payment
		""",
		query_values,
		as_dict=True,
	)

	return data
