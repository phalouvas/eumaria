// Copyright (c) 2024, KAINOTOMO PH LTD and contributors
// For license information, please see license.txt

// Override calendar view configuration to ensure color from Appointment Type displays correctly
frappe.views.calendar["Patient Appointment"] = {
	field_map: {
		start: "start",
		end: "end",
		id: "name",
		title: "patient",
		allDay: "allDay",
		color: "color", // Maps to color field from Appointment Type via get_events LEFT JOIN
	},
	order_by: "appointment_date",
	gantt: true,
	options: {
		eventDisplay: "block",
	},
	get_events_method:
		"healthcare.healthcare.doctype.patient_appointment.patient_appointment.get_events",
	update_event_method: "eumaria.healthcare.patient_appointment.update_patient_appointment_from_calendar",
};
