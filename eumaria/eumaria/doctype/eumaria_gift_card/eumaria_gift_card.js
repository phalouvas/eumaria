// Copyright (c) 2026, KAINOTOMO PH LTD and contributors
// For license information, please see license.txt

frappe.ui.form.on("Eumaria Gift Card", {
	refresh(frm) {
		// Add button to open linked Payment Entry
		if (frm.doc.payment_entry) {
			frm.add_custom_button(__("Open Payment Entry"), function() {
				frappe.set_route("Form", "Payment Entry", frm.doc.payment_entry);
			}, __("View"));
		}
	},
});
