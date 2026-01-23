frappe.ui.form.on('Patient Appointment', {
	refresh(frm) {
		// Only on saved docs
		if (frm.is_new() || frm.is_dirty()) {
			return;
		}

		// Check Healthcare Settings toggle first
		frappe.db
			.get_single_value('Healthcare Settings', 'send_appointment_confirmation')
			.then((enabled) => {
				if (!enabled) return;
				if (!is_future_appointment(frm)) return;

				frm.add_custom_button(
					__('Send SMS'),
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
					__('Actions'),
				);
			});
	},
});

function is_future_appointment(frm) {
	const { appointment_date: date, appointment_time: time } = frm.doc;
	if (!date) return false;
	const appointmentDateTime = frappe.datetime.str_to_obj(`${date} ${time || '00:00:00'}`);
	const now = frappe.datetime.str_to_obj(frappe.datetime.now_datetime());
	return appointmentDateTime > now;
}
