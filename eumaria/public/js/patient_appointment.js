// Copyright (c) 2026, KAINOTOMO PH LTD and contributors
// For license information, please see license.txt

frappe.ui.form.on('Patient Appointment', {
	refresh: function(frm) {
		// Add custom button for group billing
		if (frm.doc.is_group_session && frm.doc.attendees && frm.doc.attendees.length > 0 && !frm.doc.invoiced) {
			frm.add_custom_button(__('Create Group Invoices'), function() {
				create_group_invoices(frm);
			}, __('Actions'));
		}
		
		// Show attendee count in indicator
		if (frm.doc.is_group_session && frm.doc.attendees) {
			let attended_count = frm.doc.attendees.filter(a => a.attended).length;
			let total_count = frm.doc.attendees.length;
			frm.dashboard.add_indicator(__('Attendees: {0}/{1}', [attended_count, total_count]), 'blue');
		}
	},
	
	is_group_session: function(frm) {
		// Toggle patient field requirement based on group session
		if (frm.doc.is_group_session) {
			frm.set_df_property('patient', 'reqd', 0);
			frm.set_df_property('patient', 'read_only', 1);
			
			// Clear patient if switching to group
			if (!frm.doc.attendees || frm.doc.attendees.length === 0) {
				frm.set_value('patient', '');
			}
		} else {
			frm.set_df_property('patient', 'reqd', 1);
			frm.set_df_property('patient', 'read_only', 0);
		}
		frm.refresh_field('patient');
	},
	
	attendees_on_form_rendered: function(frm) {
		// Refresh title when attendees change
		update_appointment_title(frm);
	}
});

// Child table events
frappe.ui.form.on('Group Appointment Attendee', {
	patient: function(frm, cdt, cdn) {
		// Check for duplicate patients
		let row = locals[cdt][cdn];
		if (row.patient) {
			let duplicate = frm.doc.attendees.find(a => 
				a.patient === row.patient && a.name !== row.name
			);
			if (duplicate) {
				frappe.msgprint(__('Patient {0} is already added to attendees list', [row.patient_name || row.patient]));
				frappe.model.set_value(cdt, cdn, 'patient', '');
				return;
			}
		}
		
		update_appointment_title(frm);
		// Auto-set first attendee as primary patient for compatibility
		if (frm.doc.is_group_session && frm.doc.attendees && frm.doc.attendees.length > 0) {
			let first_attendee = frm.doc.attendees[0];
			if (first_attendee.patient && !frm.doc.patient) {
				frm.set_value('patient', first_attendee.patient);
			}
		}
	},
	
	attendees_remove: function(frm, cdt, cdn) {
		update_appointment_title(frm);
	},
	
	attended: function(frm, cdt, cdn) {
		// Update dashboard indicator
		frm.trigger('refresh');
	}
});

function update_appointment_title(frm) {
	if (frm.doc.is_group_session && frm.doc.attendees) {
		let names = [];
		frm.doc.attendees.forEach(function(attendee) {
			if (attendee.patient_name) {
				names.push(attendee.patient_name);
			}
		});
		
		if (names.length > 0) {
			let base_title = 'Group Session';
			if (frm.doc.appointment_type) {
				base_title = frm.doc.appointment_type + ' - Group';
			}
			
			let title = base_title + ': ' + names.join(', ');
			frm.set_value('title', title);
		}
	}
}

function create_group_invoices(frm) {
	frappe.confirm(
		__('Create invoices for all {0} attendees?', [frm.doc.attendees.length]),
		function() {
			frappe.call({
				method: 'eumaria.physiotherapy.billing.create_group_invoices',
				args: {
					appointment_name: frm.doc.name
				},
				freeze: true,
				freeze_message: __('Creating Invoices...'),
				callback: function(r) {
					if (r.message && r.message.length > 0) {
						frm.reload_doc();
						
						// Show list of created invoices
						frappe.msgprint({
							title: __('Invoices Created'),
							indicator: 'green',
							message: __('Created {0} invoices. Please set prices and submit them.', [r.message.length])
						});
						
						// Optionally open first invoice
						if (r.message.length === 1) {
							frappe.set_route('Form', 'Sales Invoice', r.message[0]);
						} else {
							// Show list of invoices
							frappe.route_options = {
								"patient_appointment": frm.doc.name
							};
							frappe.set_route('List', 'Sales Invoice');
						}
					}
				},
				error: function(r) {
					frappe.msgprint(__('Failed to create invoices. Please check error log.'));
				}
			});
		}
	);
}
