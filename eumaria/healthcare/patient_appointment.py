import frappe
import json
from frappe.utils import getdate, get_time
import datetime
from frappe.utils.data import flt


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
