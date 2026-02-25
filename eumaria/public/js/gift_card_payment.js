// Gift Card Payment Integration for Patient Appointments
// Monkey-patches the existing healthcare payment dialog to add gift card support

frappe.provide("eumaria.gift_card");

// Store original functions
let original_make_payment = null;
let original_show_payment_dialog = null;

// Initialize gift card payment system
eumaria.gift_card.init = function() {
	// Monkey-patch make_payment function
	if (typeof make_payment === 'function' && !original_make_payment) {
		original_make_payment = make_payment;
		make_payment = eumaria.gift_card.make_payment;
	}
	
	// Monkey-patch show_payment_dialog function
	if (typeof show_payment_dialog === 'function' && !original_show_payment_dialog) {
		original_show_payment_dialog = show_payment_dialog;
		show_payment_dialog = eumaria.gift_card.show_payment_dialog;
	}
	
	// Add gift card field change handlers to Patient Appointment form
	frappe.ui.form.on('Patient Appointment', {
		use_gift_card: function(frm) {
			eumaria.gift_card.handle_use_gift_card_change(frm);
		},
		selected_gift_card: function(frm) {
			eumaria.gift_card.handle_gift_card_selection(frm);
		},
		patient: function(frm) {
			// When patient changes, update gift card filter
			eumaria.gift_card.update_gift_card_filter(frm);
		}
	});
};

// Handle use_gift_card field change
eumaria.gift_card.handle_use_gift_card_change = function(frm) {
	if (frm.doc.use_gift_card) {
		// Clear mode_of_payment when using gift card
		frm.set_value("mode_of_payment", "");
	} else {
		// Clear gift card fields when not using gift card
		frm.set_value("selected_gift_card", "");
		frm.set_value("gift_card_balance", 0);
	}
};

// Handle gift card selection
eumaria.gift_card.handle_gift_card_selection = async function(frm) {
	if (frm.doc.selected_gift_card) {
		// Get gift card balance
		const balance = await eumaria.gift_card.get_gift_card_balance(frm.doc.selected_gift_card);
		if (balance.success) {
			frm.set_value("gift_card_balance", balance.balance);
		}
	} else {
		frm.set_value("gift_card_balance", 0);
	}
};

// Update gift card filter based on patient
eumaria.gift_card.update_gift_card_filter = function(frm) {
	if (frm.doc.patient) {
		frappe.db.get_value("Patient", frm.doc.patient, "customer").then(r => {
			if (r.message.customer) {
				frm.fields_dict.selected_gift_card.get_query = function() {
					return {
						filters: {
							customer: r.message.customer,
							disabled: 0,
							docstatus: 1,
							remaining_amount: [">", 0]  // Only show gift cards with positive balance
						}
					};
				};
			}
		});
	}
};

// Override make_payment function
eumaria.gift_card.make_payment = function(frm, automate_invoicing) {
	if (automate_invoicing) {
		eumaria.gift_card.make_registration(frm, automate_invoicing);
	}
};

// Override make_registration function
eumaria.gift_card.make_registration = function(frm, automate_invoicing) {
	if (automate_invoicing == true && !frm.doc.paid_amount) {
		frappe.throw({
			title: __("Not Allowed"),
			message: __("Please set the Paid Amount first"),
		});
	}

	let fields = [
		{
			label: "Patient",
			fieldname: "patient",
			fieldtype: "Data",
			read_only: true,
		},
		{
			label: "Mode of Payment",
			fieldname: "mode_of_payment",
			fieldtype: "Link",
			options: "Mode of Payment",
			reqd: 0,
			depends_on: "eval:!doc.use_gift_card",
			mandatory_depends_on: "eval:!doc.use_gift_card",
		},
		{
			fieldtype: "Column Break",
		},
		{
			label: "Consultation Charge",
			fieldname: "consultation_charge",
			fieldtype: "Currency",
			read_only: true,
		},
		{
			label: "Total Payable",
			fieldname: "total_payable",
			fieldtype: "Currency",
			read_only: true,
		},
		// Gift Card Section
		{
			label: __("Gift Card Payment"),
			fieldtype: "Section Break",
			collapsible: 1,
		},
		{
			label: "Use Gift Card",
			fieldname: "use_gift_card",
			fieldtype: "Check",
			default: 0,
			description: __("Check to pay using gift card"),
		},
		{
			label: "Gift Card",
			fieldname: "gift_card",
			fieldtype: "Link",
			options: "Eumaria Gift Card",
			reqd: 0,
			depends_on: "eval:doc.use_gift_card",
			mandatory_depends_on: "eval:doc.use_gift_card",
			description: __("Select gift card for payment"),
		},
		{
			fieldtype: "Column Break",
		},
		{
			label: "Gift Card Balance",
			fieldname: "gift_card_balance",
			fieldtype: "Currency",
			read_only: true,
			depends_on: "eval:doc.use_gift_card && doc.gift_card",
			description: __("Remaining balance on selected gift card"),
		},
		{
			label: "Gift Card Status",
			fieldname: "gift_card_status",
			fieldtype: "Data",
			read_only: true,
			depends_on: "eval:doc.use_gift_card && doc.gift_card",
			description: __("Gift card validation status"),
		},
		{
			label: __("Additional Discount"),
			fieldtype: "Section Break",
			collapsible: 1,
		},
		{
			label: "Discount Percentage",
			fieldname: "discount_percentage",
			fieldtype: "Percent",
			default: 0,
		},
		{
			fieldtype: "Column Break",
		},
		{
			label: "Discount Amount",
			fieldname: "discount_amount",
			fieldtype: "Currency",
			default: 0,
		},
	];

	if (frm.doc.appointment_for == "Practitioner") {
		let pract_dict = {
			label: "Practitioner",
			fieldname: "practitioner",
			fieldtype: "Data",
			read_only: true,
		};
		fields.splice(3, 0, pract_dict);
	} else if (frm.doc.appointment_for == "Service Unit") {
		let su_dict = {
			label: "Service Unit",
			fieldname: "service_unit",
			fieldtype: "Data",
			read_only: true,
		};
		fields.splice(3, 0, su_dict);
	} else if (frm.doc.appointment_for == "Department") {
		let dept_dict = {
			label: "Department",
			fieldname: "department",
			fieldtype: "Data",
			read_only: true,
		};
		fields.splice(3, 0, dept_dict);
	}

	if (automate_invoicing) {
		eumaria.gift_card.show_payment_dialog(frm, fields);
	}
};

// Override show_payment_dialog function
eumaria.gift_card.show_payment_dialog = function(frm, fields) {
	let d = new frappe.ui.Dialog({
		title: "Enter Payment Details",
		fields: fields,
		primary_action_label: "Create Invoice",
		primary_action: async function(values) {
			// Validate payment method selection
			if (!values.use_gift_card && !values.mode_of_payment) {
				frappe.msgprint({
					title: __("Payment Method Required"),
					message: __("Please select either a Mode of Payment or use a Gift Card."),
					indicator: "red"
				});
				return;
			}

			if (values.use_gift_card && !values.gift_card) {
				frappe.msgprint({
					title: __("Gift Card Required"),
					message: __("Please select a gift card when using gift card payment."),
					indicator: "red"
				});
				return;
			}

			// Validate gift card if used
			if (values.use_gift_card && values.gift_card) {
				const validation = await eumaria.gift_card.validate_gift_card_in_dialog(
					values.gift_card,
					values.total_payable
				);

				if (!validation.valid) {
					frappe.msgprint({
						title: __("Gift Card Validation Failed"),
						message: validation.message,
						indicator: "red"
					});
					return;
				}
			}
			
			// Update appointment with gift card info
			if (values.use_gift_card) {
				frm.set_value("use_gift_card", 1);
				frm.set_value("selected_gift_card", values.gift_card);
				frm.set_value("mode_of_payment", "");
			} else {
				frm.set_value("use_gift_card", 0);
				frm.set_value("selected_gift_card", "");
				frm.set_value("mode_of_payment", values.mode_of_payment);
			}
			
			if (frm.is_dirty()) {
				await frm.save();
			}
			
			// Call invoice creation with gift card parameter
			frappe.call({
				method: "eumaria.overrides.invoice_creation.invoice_appointment",
				args: {
					appointment_name: frm.doc.name,
					discount_percentage: values.discount_percentage,
					discount_amount: values.discount_amount,
				},
				callback: async function(data) {
					if (!data.exc) {
						await frm.reload_doc();
						if (frm.doc.ref_sales_invoice) {
							d.get_field("mode_of_payment").$input.prop("disabled", true);
							d.get_field("use_gift_card").$input.prop("disabled", true);
							d.get_field("gift_card").$input.prop("disabled", true);
							d.get_field("discount_percentage").$input.prop("disabled", true);
							d.get_field("discount_amount").$input.prop("disabled", true);
							d.get_primary_btn().attr("disabled", true);
							d.get_secondary_btn().attr("disabled", false);
						}
					}
				},
			});
		},
		secondary_action_label: __(`<svg class="icon  icon-sm" style="">
			<use class="" href="#icon-printer"></use>
		</svg>`),
		secondary_action() {
			window.open("/app/print/Sales Invoice/" + frm.doc.ref_sales_invoice, "_blank");
			d.hide();
		},
	});
	
	// Set gift card filter based on patient's customer
	if (frm.doc.patient) {
		frappe.db.get_value("Patient", frm.doc.patient, "customer").then(r => {
			if (r.message.customer) {
				d.fields_dict.gift_card.df.get_query = function() {
					return {
						filters: {
							customer: r.message.customer,
							disabled: 0,
							docstatus: 1,
							remaining_amount: [">", 0]  // Only show gift cards with positive balance
						}
					};
				};
			}
		});
	}
	
	d.fields_dict["mode_of_payment"].df.onchange = () => {
		if (d.get_value("mode_of_payment")) {
			// If mode of payment selected, uncheck gift card
			d.set_value("use_gift_card", 0);
			d.set_value("gift_card", "");
			d.set_value("gift_card_balance", 0);
			d.set_value("gift_card_status", "");
		}
	};
	
	d.fields_dict["use_gift_card"].df.onchange = () => {
		const use_gift_card = d.get_value("use_gift_card");
		if (use_gift_card) {
			// If gift card selected, clear mode of payment
			d.set_value("mode_of_payment", "");
		}
		// Refresh field dependencies
		d.refresh();
	};
	
	d.fields_dict["gift_card"].df.onchange = async () => {
		const gift_card = d.get_value("gift_card");
		const total_payable = d.get_value("total_payable");
		
		if (gift_card && total_payable) {
			const validation = await eumaria.gift_card.validate_gift_card_in_dialog(gift_card, total_payable);
			
			if (validation.valid) {
				d.set_value("gift_card_balance", validation.remaining_amount);
				d.set_value("gift_card_status", __("Valid"));
				d.get_field("gift_card_status").$wrapper.css("color", "green");
			} else {
				d.set_value("gift_card_balance", 0);
				d.set_value("gift_card_status", validation.message);
				d.get_field("gift_card_status").$wrapper.css("color", "red");
			}
		} else if (gift_card) {
			// Just get balance without validation
			const balance = await eumaria.gift_card.get_gift_card_balance(gift_card);
			if (balance.success) {
				d.set_value("gift_card_balance", balance.balance);
				d.set_value("gift_card_status", __("Balance: {0}", [balance.balance]));
				d.get_field("gift_card_status").$wrapper.css("color", "blue");
			}
		} else {
			d.set_value("gift_card_balance", 0);
			d.set_value("gift_card_status", "");
		}
	};
	
	d.get_secondary_btn().attr("disabled", true);
	d.set_values({
		patient: frm.doc.patient_name,
		consultation_charge: frm.doc.paid_amount,
		total_payable: frm.doc.paid_amount,
		use_gift_card: frm.doc.use_gift_card || 0,
		gift_card: frm.doc.selected_gift_card || "",
	});

	if (frm.doc.appointment_for == "Practitioner") {
		d.set_value("practitioner", frm.doc.practitioner_name);
	} else if (frm.doc.appointment_for == "Service Unit") {
		d.set_value("service_unit", frm.doc.service_unit);
	} else if (frm.doc.appointment_for == "Department") {
		d.set_value("department", frm.doc.department);
	}

	if (frm.doc.mode_of_payment && !frm.doc.use_gift_card) {
		d.set_value("mode_of_payment", frm.doc.mode_of_payment);
	}
	
	if (frm.doc.selected_gift_card && frm.doc.use_gift_card) {
		// Trigger gift card change to load balance
		setTimeout(() => {
			d.fields_dict.gift_card.df.onchange();
		}, 100);
	}
	
	d.show();

	d.fields_dict["discount_percentage"].df.onchange = () =>
		eumaria.gift_card.validate_discount(d, "discount_percentage");
	d.fields_dict["discount_amount"].df.onchange = () =>
		eumaria.gift_card.validate_discount(d, "discount_amount");
};

// Validate gift card in dialog
eumaria.gift_card.validate_gift_card_in_dialog = async function(gift_card, amount) {
	return new Promise((resolve) => {
		frappe.call({
			method: "eumaria.api.gift_card.validate_gift_card",
			args: {
				gift_card: gift_card,
				amount: amount
			},
			callback: function(r) {
				resolve(r.message);
			}
		});
	});
};

// Get gift card balance
eumaria.gift_card.get_gift_card_balance = async function(gift_card) {
	return new Promise((resolve) => {
		frappe.call({
			method: "eumaria.api.gift_card.get_gift_card_balance",
			args: {
				gift_card: gift_card
			},
			callback: function(r) {
				resolve(r.message);
			}
		});
	});
};

// Revalidate gift card after discount change
eumaria.gift_card.revalidate_gift_card_on_discount_change = function(d) {
	const gift_card = d.get_value("gift_card");
	const use_gift_card = d.get_value("use_gift_card");
	const total_payable = d.get_value("total_payable");

	if (use_gift_card && gift_card && total_payable) {
		// Trigger gift card validation
		d.fields_dict.gift_card.df.onchange();
	}
};

// Validate discount (copied from original)
eumaria.gift_card.validate_discount = function(d, field) {
	let message = "";
	let discount_percentage = d.get_value("discount_percentage");
	let discount_amount = d.get_value("discount_amount");
	let consultation_charge = d.get_value("consultation_charge");

	if (field === "discount_percentage") {
		if (discount_percentage > 100 || discount_percentage < 0) {
			d.get_primary_btn().attr("disabled", true);
			message = "Invalid discount percentage";
		} else {
			d.get_primary_btn().attr("disabled", false);
			// Store in dialog data instead of global frm
			d.dialog_data = d.dialog_data || {};
			d.dialog_data.via_discount_percentage = true;
			if (discount_percentage && discount_amount) {
				d.set_value("discount_amount", 0);
			}
			discount_amount = consultation_charge * (discount_percentage / 100);

			d.set_values({
				discount_amount: discount_amount,
				total_payable: consultation_charge - discount_amount,
			}).then(() => {
				delete d.dialog_data.via_discount_percentage;
			}).then(() => {
				eumaria.gift_card.revalidate_gift_card_on_discount_change(d);
			});
		}
	} else if (field === "discount_amount") {
		if (consultation_charge < discount_amount || discount_amount < 0) {
			d.get_primary_btn().attr("disabled", true);
			message = "Discount amount should not be more than Consultation Charge";
		} else {
			d.get_primary_btn().attr("disabled", false);
			if (!(d.dialog_data && d.dialog_data.via_discount_percentage)) {
				discount_percentage = (discount_amount / consultation_charge) * 100;
				d.set_values({
					discount_percentage: discount_percentage,
					total_payable: consultation_charge - discount_amount,
				}).then(() => {
					eumaria.gift_card.revalidate_gift_card_on_discount_change(d);
				});
			}
		}
	}
	
	// Show message if there is one
	if (message) {
		frappe.show_alert({
			message: message,
			indicator: 'red'
		}, 3);
	}
};

// Initialize the gift card payment system when the page loads
$(document).ready(function() {
	// Wait a bit to ensure all Frappe components are loaded
	setTimeout(function() {
		eumaria.gift_card.init();
	}, 1000);
});