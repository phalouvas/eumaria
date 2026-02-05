// Copyright (c) 2024, KAINOTOMO PH LTD and contributors
// For license information, please see license.txt

// Override calendar view configuration to ensure color from Appointment Type displays correctly
frappe.views.calendar["Patient Appointment"] = {
	field_map: {
		start: "start",
		end: "end",
		id: "name",
		title: "title",
		allDay: "allDay",
		color: "color", // Maps to color field from Appointment Type via get_events LEFT JOIN
	},
	order_by: "appointment_date",
	gantt: true,
	options: {
		eventDisplay: "block",
		eventContent(info) {
			if (!info?.event?.extendedProps?.is_unavailability) {
				return true;
			}

			const wrapper = document.createElement("div");
			wrapper.classList.add("unavailability-content");

			const title = document.createElement("div");
			title.classList.add("unavailability-title");
			title.textContent = info.event.title || "Unavailable";
			wrapper.appendChild(title);

			const noteText = info.event.extendedProps?.note;
			if (noteText) {
				const note = document.createElement("div");
				note.classList.add("unavailability-note");
				note.textContent = noteText;
				wrapper.appendChild(note);
			}

			return { domNodes: [wrapper] };
		},
		eventDidMount(info) {
			const tooltip = info?.event?.extendedProps?.tooltip;
			if (tooltip) {
				info.el.setAttribute("title", tooltip);
			}
		},
		eventClick(info) {
			if (info?.event?.extendedProps?.is_unavailability) {
				return;
			}
			const doctype = info.doctype || "Patient Appointment";
			if (frappe.model.can_read(doctype)) {
				frappe.set_route("Form", doctype, info.event.id);
			}
		},
	},
	get_events_method: "eumaria.healthcare.patient_appointment.get_events_with_availability",
	update_event_method: "eumaria.healthcare.patient_appointment.update_patient_appointment_from_calendar",
};
