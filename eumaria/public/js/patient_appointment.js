frappe.ui.form.on('Patient Appointment', {
	refresh(frm) {
		// Only on saved docs
		if (frm.is_new() || frm.is_dirty()) {
			return;
		}

		if (!is_future_appointment(frm)) {
			return;
		}

		frm.add_custom_button(
			__('Send Confirmation SMS'),
			() => {
				frappe.call({
					method: 'eumaria.overrides.patient_appointment.send_appointment_sms',
					args: { appointment_name: frm.doc.name },
					freeze: true,
					freeze_message: __('Sending SMS...'),
					callback: (r) => {
						if (!r.exc) {
							frm.reload_doc();
						}
					},
				});
			},
			__('SMS')
		);

		frm.add_custom_button(
			__('Compose SMS'),
			() => {
				const dialog = new frappe.ui.Dialog({
					title: __('Compose SMS'),
					fields: [
						{
							fieldname: 'message',
							fieldtype: 'Small Text',
							label: __('Message'),
							reqd: 1,
						},
					],
					primary_action_label: __('Send'),
					primary_action: (values) => {
						frappe.call({
							method: 'eumaria.overrides.patient_appointment.send_custom_appointment_sms',
							args: {
								appointment_name: frm.doc.name,
								message: values.message,
							},
							freeze: true,
							freeze_message: __('Sending SMS...'),
							callback: (r) => {
								if (!r.exc) {
									dialog.hide();
									frm.reload_doc();
								}
							},
						});
					},
				});

				dialog.show();
			},
			__('SMS')
		);
	},
});

function is_future_appointment(frm) {
	const { appointment_date: date, appointment_time: time } = frm.doc;
	if (!date) return false;
	const appointmentDateTime = frappe.datetime.str_to_obj(`${date} ${time || '00:00:00'}`);
	const now = frappe.datetime.str_to_obj(frappe.datetime.now_datetime());
	return appointmentDateTime > now;
}
