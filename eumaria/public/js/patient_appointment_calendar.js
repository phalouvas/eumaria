// Copyright (c) 2024, KAINOTOMO PH LTD and contributors
// For license information, please see license.txt

// Override calendar view configuration to ensure color from Appointment Type displays correctly
function escapeHTML(value) {
	if (value === null || value === undefined) {
		return "";
	}
	if (frappe?.utils?.escape_html) {
		return frappe.utils.escape_html(String(value));
	}
	return String(value)
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;")
		.replace(/'/g, "&#39;");
}

function buildPatientPopoverContent(props) {
	const rows = [];
	if (props?.patient_dob) {
		rows.push({ label: "DOB", value: props.patient_dob });
	}
	if (props?.patient_uid) {
		rows.push({ label: "UID", value: props.patient_uid });
	}
	if (props?.patient_mobile) {
		rows.push({ label: "Mobile", value: props.patient_mobile });
	}

	if (!rows.length) {
		return "";
	}

	return rows
		.map(
			(row) =>
				`<div class="eumaria-appointment-popover-row"><span class="label">${escapeHTML(
					row.label
				)}:</span><span class="value">${escapeHTML(row.value)}</span></div>`
		)
		.join("");
}

let activeAppointmentTooltip = null;
let activeAppointmentTarget = null;
let lastAppointmentMouse = { x: 0, y: 0 };

function ensureAppointmentTooltip() {
	if (activeAppointmentTooltip) {
		return activeAppointmentTooltip;
	}
	const tooltip = document.createElement("div");
	tooltip.className = "eumaria-appointment-tooltip";
	tooltip.setAttribute("role", "tooltip");
	tooltip.style.display = "none";
	document.body.appendChild(tooltip);
	activeAppointmentTooltip = tooltip;
	return tooltip;
}

function showAppointmentTooltip(targetEl, title, content, event) {
	if (!content) {
		return;
	}
	const tooltip = ensureAppointmentTooltip();
	activeAppointmentTarget = targetEl;
	tooltip.innerHTML = `<div class="eumaria-appointment-tooltip-title">${escapeHTML(
		title || "Patient"
	)}</div>${content}`;
	tooltip.style.display = "block";
	if (event?.clientX !== undefined && event?.clientY !== undefined) {
		lastAppointmentMouse = { x: event.clientX, y: event.clientY };
	}
	positionAppointmentTooltip(event, targetEl);
}

function hideAppointmentTooltip(targetEl) {
	if (!activeAppointmentTooltip || activeAppointmentTarget !== targetEl) {
		return;
	}
	activeAppointmentTooltip.style.display = "none";
	activeAppointmentTooltip.innerHTML = "";
	activeAppointmentTarget = null;
}

function positionAppointmentTooltip(event, targetEl) {
	if (!activeAppointmentTooltip || activeAppointmentTooltip.style.display === "none") {
		return;
	}
	const offsetX = 12;
	const offsetY = 14;
	const viewportPadding = 8;
	const tooltipRect = activeAppointmentTooltip.getBoundingClientRect();
	let mouseX = event?.clientX;
	let mouseY = event?.clientY;
	if (mouseX === undefined || mouseY === undefined) {
		mouseX = lastAppointmentMouse.x;
		mouseY = lastAppointmentMouse.y;
	}
	if ((!mouseX && mouseX !== 0) || (!mouseY && mouseY !== 0)) {
		const rect = targetEl?.getBoundingClientRect();
		if (rect) {
			mouseX = rect.right;
			mouseY = rect.top;
		} else {
			mouseX = viewportPadding;
			mouseY = viewportPadding;
		}
	}

	let left = mouseX + offsetX;
	let top = mouseY + offsetY;

	const maxLeft = window.innerWidth - tooltipRect.width - viewportPadding;
	const maxTop = window.innerHeight - tooltipRect.height - viewportPadding;
	if (left > maxLeft) {
		left = Math.max(viewportPadding, event.clientX - tooltipRect.width - offsetX);
	}
	if (top > maxTop) {
		top = Math.max(viewportPadding, event.clientY - tooltipRect.height - offsetY);
	}

	activeAppointmentTooltip.style.left = `${left}px`;
	activeAppointmentTooltip.style.top = `${top}px`;
	activeAppointmentTooltip.style.right = "auto";
	activeAppointmentTooltip.style.bottom = "auto";
}

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
			const props = info?.event?.extendedProps || {};
			if (props.is_unavailability) {
				const tooltip = props.tooltip;
				if (tooltip) {
					info.el.setAttribute("title", tooltip);
				}
				return;
			}
			if (props.is_holiday) {
				return;
			}

			const title = props.patient_name || info.event.title;
			const content = buildPatientPopoverContent(props);
			if (!content) {
				return;
			}
			const showHandler = (event) => {
				showAppointmentTooltip(info.el, title, content, event);
			};
			const moveHandler = (event) => {
				if (event?.clientX !== undefined && event?.clientY !== undefined) {
					lastAppointmentMouse = { x: event.clientX, y: event.clientY };
				}
				positionAppointmentTooltip(event);
			};
			const hideHandler = () => {
				hideAppointmentTooltip(info.el);
			};

			info.el.addEventListener("mouseenter", showHandler);
			info.el.addEventListener("mousemove", moveHandler);
			info.el.addEventListener("mouseleave", hideHandler);
			info.el._eumariaTooltipHandlers = { showHandler, moveHandler, hideHandler };
		},
		eventWillUnmount(info) {
			const handlers = info?.el?._eumariaTooltipHandlers;
			if (!handlers) {
				return;
			}
			info.el.removeEventListener("mouseenter", handlers.showHandler);
			info.el.removeEventListener("mousemove", handlers.moveHandler);
			info.el.removeEventListener("mouseleave", handlers.hideHandler);
			delete info.el._eumariaTooltipHandlers;
			hideAppointmentTooltip(info.el);
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
