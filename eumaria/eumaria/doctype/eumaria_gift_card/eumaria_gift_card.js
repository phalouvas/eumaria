// Copyright (c) 2026, KAINOTOMO PH LTD and contributors
// For license information, please see license.txt

frappe.ui.form.on("Eumaria Gift Card", {
	onload(frm) {
		if (!frm.is_new()) {
			return;
		}

		const today = frappe.datetime.get_today();

		if (!frm.doc.starts_on) {
			frm.set_value("starts_on", today);
		}

		if (!frm.doc.ends_on) {
			frm.set_value("ends_on", frappe.datetime.add_months(today, 6));
		}
	},

	refresh(frm) {
		// Add button to open linked Payment Entry
		if (frm.doc.payment_entry) {
			frm.add_custom_button(__("Open Payment Entry"), function() {
				frappe.set_route("Form", "Payment Entry", frm.doc.payment_entry);
			}, __("View"));
		}
	},
});
