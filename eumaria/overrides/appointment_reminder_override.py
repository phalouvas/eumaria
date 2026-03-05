import datetime

import frappe
from frappe import _


HEALTHCARE_REMINDER_METHOD = (
    "healthcare.healthcare.doctype.patient_appointment.patient_appointment.send_appointment_reminder"
)
EUMARIA_REMINDER_METHOD = "eumaria.overrides.appointment_reminder_override.send_appointment_reminder"


def _to_timedelta(value) -> datetime.timedelta:
    """Normalize Time field values returned by Frappe/DB into timedelta."""
    if not value:
        return datetime.timedelta(0)

    if isinstance(value, datetime.timedelta):
        return value

    if isinstance(value, datetime.time):
        return datetime.timedelta(hours=value.hour, minutes=value.minute, seconds=value.second)

    if isinstance(value, str):
        parsed = datetime.datetime.strptime(value, "%H:%M:%S")
        return datetime.timedelta(hours=parsed.hour, minutes=parsed.minute, seconds=parsed.second)

    frappe.throw(_("Invalid value in Healthcare Settings: Remind Before"))


def send_appointment_reminder():
    """Patched replacement for Healthcare reminder job.

    Fixes handling of `remind_before` when Frappe returns it as `datetime.timedelta`.
    """
    
    if not frappe.db.get_single_value("Healthcare Settings", "send_appointment_reminder"):
        return

    remind_before = frappe.db.get_single_value("Healthcare Settings", "remind_before")
    remind_delta = _to_timedelta(remind_before)

    now_dt = frappe.utils.now_datetime()
    reminder_dt = now_dt + remind_delta

    if reminder_dt <= now_dt:
        return

    appointment_list = frappe.db.get_all(
        "Patient Appointment",
        {
            "appointment_datetime": ["between", (now_dt, reminder_dt)],
            "reminded": 0,
            "status": ["!=", "Cancelled"],
        },
        pluck="name",
    )

    message = frappe.db.get_single_value("Healthcare Settings", "appointment_reminder_msg")
    if not message:
        return

    from healthcare.healthcare.doctype.patient_appointment import patient_appointment as core_patient_appointment

    for appointment_name in appointment_list:
        doc = frappe.get_doc("Patient Appointment", appointment_name)
        try:
            core_patient_appointment.send_message(doc, message)
            frappe.db.set_value("Patient Appointment", doc.name, "reminded", 1)
        except Exception:
            frappe.log_error(frappe.get_traceback(), _("Appointment Reminder Message Not Sent"))


def ensure_scheduler_uses_eumaria_reminder() -> None:
    """Point Healthcare reminder scheduler entry to Eumaria implementation."""
    job_names = frappe.get_all(
        "Scheduled Job Type",
        filters={"method": ["in", [HEALTHCARE_REMINDER_METHOD, EUMARIA_REMINDER_METHOD]]},
        pluck="name",
    )

    for job_name in job_names:
        method = frappe.db.get_value("Scheduled Job Type", job_name, "method")
        if method == HEALTHCARE_REMINDER_METHOD:
            frappe.db.set_value("Scheduled Job Type", job_name, "method", EUMARIA_REMINDER_METHOD)


def execute() -> None:
    """Patch entrypoint for migration scripts."""
    ensure_scheduler_uses_eumaria_reminder()
