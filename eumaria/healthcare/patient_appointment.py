import frappe
import json
import datetime
from frappe.utils import add_days, getdate, get_time
from frappe.utils.data import flt
from healthcare.healthcare.doctype.patient_appointment.patient_appointment import (
	get_events as healthcare_get_events,
)


@frappe.whitelist()
def update_patient_appointment_from_calendar(args):
	"""Update Patient Appointment date/time from calendar drag-drop.
	
	Args:
		args: JSON string with name, start (datetime string), end (datetime string)
	"""
	# Parse JSON string if needed
	if isinstance(args, str):
		args = json.loads(args)
	
	args = frappe._dict(args)
	name = args.get("name")
	start = args.get("start")
	
	if not name or not start:
		frappe.throw("Missing appointment name or start time")
	
	doc = frappe.get_doc("Patient Appointment", name)
	
	# Parse datetime string to date and time
	start_dt = frappe.utils.get_datetime(start)
	
	doc.appointment_date = start_dt.date()
	doc.appointment_time = start_dt.time()
	
	doc.save(ignore_permissions=True)
	
	return {"name": name}


def _parse_filters(filters):
	if isinstance(filters, str):
		filters = json.loads(filters)
	if isinstance(filters, (list, tuple)):
		parsed = {}
		for item in filters:
			if not isinstance(item, (list, tuple)) or len(item) < 4:
				continue
			field = item[1]
			value = item[3]
			if not field:
				continue
			if isinstance(value, (list, tuple)):
				values = [v for v in value if v]
			else:
				values = [value] if value not in (None, "") else []
			if not values:
				continue
			existing = parsed.get(field)
			if existing is None:
				parsed[field] = values if len(values) > 1 else values[0]
			elif isinstance(existing, (list, tuple)):
				parsed[field] = list(existing) + values
			else:
				parsed[field] = [existing] + values
		return frappe._dict(parsed)
	return frappe._dict(filters or {})


def _unique_list(values):
	return list(dict.fromkeys([value for value in values if value]))


def _collect_scope_values(value):
	if not value:
		return []
	if isinstance(value, (list, tuple)):
		return [item for item in value if item]
	return [value]


def _iter_date_range(start_date, end_date):
	current = start_date
	while current <= end_date:
		yield current
		current = add_days(current, 1)


def _get_weekday_flags(availability):
	weekdays = [
		"monday",
		"tuesday",
		"wednesday",
		"thursday",
		"friday",
		"saturday",
		"sunday",
	]
	return {day for day in weekdays if getattr(availability, day, 0)}


def _iter_recurrence_dates(availability, range_start, range_end):
	start_date = getdate(availability.start_date)
	end_date = getdate(availability.end_date) if availability.end_date else range_end
	current_start = max(range_start, start_date)
	current_end = min(range_end, end_date)

	if current_start > current_end:
		return []

	repeat = availability.repeat or "Never"
	if repeat in ("Never", "Daily"):
		return list(_iter_date_range(current_start, current_end))

	if repeat == "Weekly":
		weekday_flags = _get_weekday_flags(availability)
		start_weekday = start_date.weekday()
		matched = []
		for current_date in _iter_date_range(current_start, current_end):
			weekday = current_date.strftime("%A").lower()
			if weekday_flags:
				if weekday in weekday_flags:
					matched.append(current_date)
			elif current_date.weekday() == start_weekday:
				matched.append(current_date)
		return matched

	if repeat == "Monthly":
		day_of_month = start_date.day
		return [
			current_date
			for current_date in _iter_date_range(current_start, current_end)
			if current_date.day == day_of_month
		]

	return list(_iter_date_range(current_start, current_end))


def _build_unavailability_events(start, end, filters):
	filters = _parse_filters(filters)
	range_start = getdate(start)
	range_end = getdate(end)
	scopes = _unique_list(
		_collect_scope_values(filters.get("practitioner"))
		+ _collect_scope_values(filters.get("department"))
		+ _collect_scope_values(filters.get("service_unit"))
	)

	availability_filters = {
		"type": "Unavailable",
		"docstatus": 1,
		"start_date": ("<=", range_end),
		"end_date": (">=", range_start),
		"status": "Active",
	}
	if scopes:
		availability_filters["scope"] = ["in", scopes]

	availability_records = frappe.get_all(
		"Practitioner Availability",
		fields=[
			"name",
			"scope",
			"scope_type",
			"start_date",
			"end_date",
			"start_time",
			"end_time",
			"repeat",
			"reason",
			"note",
			"duration",
			"monday",
			"tuesday",
			"wednesday",
			"thursday",
			"friday",
			"saturday",
			"sunday",
		],
		filters=availability_filters,
		order_by="start_date, start_time",
	)

	unavailability_events = []
	for availability in availability_records:
		for current_date in _iter_recurrence_dates(availability, range_start, range_end):
			start_dt = datetime.datetime.combine(current_date, datetime.time())
			if availability.start_time:
				start_dt = start_dt + availability.start_time

			end_dt = datetime.datetime.combine(current_date, datetime.time())
			if availability.end_time:
				end_dt = end_dt + availability.end_time
			elif availability.duration:
				end_dt = start_dt + datetime.timedelta(minutes=flt(availability.duration))
			else:
				end_dt = start_dt

			reason = availability.reason or "Unavailable"
			scope_label = availability.scope or "Practitioner"
			title = f"Unavailable - {scope_label}"
			if availability.reason:
				title = f"{title} ({availability.reason})"

			details = []
			if availability.reason:
				details.append(f"Reason: {availability.reason}")
			if availability.note:
				details.append(f"Note: {availability.note}")
			description = " | ".join(details)
			tooltip_parts = [title]
			if availability.note:
				tooltip_parts.append(f"Note: {availability.note}")
			if availability.reason:
				tooltip_parts.append(f"Reason: {availability.reason}")
			tooltip = "\n".join(tooltip_parts)

			unavailability_events.append(
				{
					"name": f"unavail-{availability.name}-{current_date}",
					"title": title,
					"start": start_dt,
					"end": end_dt,
					"allDay": 0,
					"editable": 0,
					"durationEditable": 0,
					"startEditable": 0,
					"color": "#efefef",
					"textColor": "#444",
					"className": ["unavailability-block"],
					"description": description,
					"tooltip": tooltip,
					"note": availability.note,
					"reason": availability.reason,
					"scope": availability.scope,
					"is_unavailability": 1,
				}
			)

	return unavailability_events


@frappe.whitelist()
def get_events_with_availability(start, end, filters=None):
	appointment_events = healthcare_get_events(start, end, filters)
	for item in appointment_events:
		item["title"] = item.get("patient") or item.get("title")

	unavailability_events = _build_unavailability_events(start, end, filters)
	return appointment_events + unavailability_events
