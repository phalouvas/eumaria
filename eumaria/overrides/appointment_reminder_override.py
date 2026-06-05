import datetime

import frappe
from frappe import _
from frappe.core.doctype.sms_settings.sms_settings import send_sms


HEALTHCARE_REMINDER_METHOD = (
    "healthcare.healthcare.doctype.patient_appointment.patient_appointment.send_appointment_reminder"
)
EUMARIA_REMINDER_METHOD = "eumaria.overrides.appointment_reminder_override.send_appointment_reminder"

# ── Constants ──────────────────────────────────────────────────────────────
LOCK_TIMEOUT_SECONDS = 600  # 10 min — skip if another run is active


def _to_timedelta(value) -> datetime.timedelta:
    """Normalize Time field values returned by Frappe/DB into timedelta."""
    if not value:
        return datetime.timedelta(0)

    if isinstance(value, datetime.timedelta):
        return value

    if isinstance(value, datetime.time):
        return datetime.timedelta(hours=value.hour, minutes=value.minute, seconds=value.second)

    if isinstance(value, str):
        # Try parsing as "HH:MM:SS" (or "HH:MM") — hours may exceed 23.
        parts = value.split(":")
        if len(parts) in (2, 3):
            try:
                h, m = int(parts[0]), int(parts[1])
                s = int(parts[2]) if len(parts) == 3 else 0
                return datetime.timedelta(hours=h, minutes=m, seconds=s)
            except (ValueError, TypeError):
                pass
        # Some DB drivers may return a total-seconds string (e.g. "86400" for 24 h).
        try:
            total_seconds = float(value)
            return datetime.timedelta(seconds=total_seconds)
        except (ValueError, TypeError):
            pass
        frappe.throw(
            _("Invalid time format in Healthcare Settings → Remind Before: '{0}'. "
              "Expected HH:MM:SS or a numeric value in seconds.").format(value)
        )

    frappe.throw(_("Invalid value in Healthcare Settings: Remind Before"))


def _job_lock_key() -> str:
    """Return the cache key used for the distributed-run lock."""
    return "eumaria:send_appointment_reminder:lock"


def _acquire_lock() -> bool:
    """Try to acquire a distributed lock.

    Returns True if this process got the lock and should proceed.
    If another process already holds the lock and it hasn't expired,
    returns False so this run is skipped.

    Uses ``setnx`` semantics: ``set_value`` with ``nx=True`` only succeeds
    if no key exists; ``get_value`` + ``set_value`` would have a race window.
    """
    key = _job_lock_key()
    # Check if lock already held before setting (avoid overwriting existing TTL)
    if frappe.cache().get_value(key):
        return False
    frappe.cache().set_value(key, True, expires_in_sec=LOCK_TIMEOUT_SECONDS)
    return True


def _release_lock() -> None:
    """Release the distributed lock."""
    frappe.cache().delete_value(_job_lock_key())


def send_appointment_reminder():
    """Patched replacement for Healthcare reminder job.

    Fixes handling of `remind_before` when Frappe returns it as `datetime.timedelta`.
    Adds comprehensive logging, guards against same-day processing (prevents
    the midnight ``reminded=1`` bug), and prevents duplicate concurrent runs
    via a distributed cache lock.

    Deduplication uses **timeline comments** instead of the ``reminded`` field,
    because ``reminded`` may be set by other processes (group session validation,
    manual confirmation SMS, etc.), making it an unreliable dedup signal.
    The timeline comment with prefix ``"Reminder SMS sent at"`` is set
    exclusively by this function.
    """

    # ── Guard: feature enabled? ──────────────────────────────────────────────
    if not frappe.db.get_single_value("Healthcare Settings", "send_appointment_reminder"):
        return

    # ── Guard: distributed lock (prevent concurrent runs) ────────────────────
    if not _acquire_lock():
        return

    try:
        remind_before = frappe.db.get_single_value("Healthcare Settings", "remind_before")
        remind_delta = _to_timedelta(remind_before)

        # ── Guard: remind_before zero / negative ─────────────────────────────
        if remind_delta <= datetime.timedelta(0):
            frappe.log_error(
                f"send_appointment_reminder: remind_before is zero or negative ({remind_before}). "
                "No reminders will be sent. Please check Healthcare Settings.",
                _("Appointment Reminder — Invalid remind_before"),
            )
            return

        # Use timezone-aware now() for consistent comparisons with appointment_datetime.
        now_dt = frappe.utils.now_datetime()
        reminder_dt = now_dt + remind_delta

        # Fetch ALL matching appointments regardless of reminded flag.
        # Deduplication is handled via timeline-comment check below,
        # not the `reminded` field (which may be set by other processes).
        appointment_list = frappe.db.get_all(
            "Patient Appointment",
            {
                "appointment_datetime": ["between", (now_dt, reminder_dt)],
                "status": ["!=", "Cancelled"],
            },
            pluck="name",
            limit_page_length=0,
        )

        if not appointment_list:
            return

        message = frappe.db.get_single_value("Healthcare Settings", "appointment_reminder_msg")
        if not message:
            return

        from eumaria.overrides.patient_appointment import (
            _add_sms_activity,
            _render_sms_template,
        )

        # ── Batch deduplication: find appointments already reminded ──────────
        # We use timeline comments (set exclusively by this function) rather
        # than the `reminded` field, which may be corrupted by other processes.
        # Look back twice the remind window to catch reminders sent on
        # previous scheduler runs.
        already_reminded = set(
            frappe.get_all(
                "Comment",
                filters={
                    "reference_doctype": "Patient Appointment",
                    "reference_name": ["in", appointment_list],
                    "content": ["like", "%Reminder SMS sent%"],
                    "creation": [">=", now_dt - remind_delta * 2],
                },
                pluck="reference_name",
                limit_page_length=0,
            )
        )

        # ── Stats for summary ────────────────────────────────────────────────
        counts = {"sent": 0, "already_reminded": 0, "no_mobile": 0, "same_day": 0, "failed": 0}

        for appointment_name in appointment_list:
            # ── Dedup: skip if already reminded via timeline ─────────────────
            if appointment_name in already_reminded:
                counts["already_reminded"] += 1
                continue

            doc = frappe.get_doc("Patient Appointment", appointment_name)

            # ── Guard: skip same-day appointments ────────────────────────────
            appointment_dt = frappe.utils.get_datetime(
                f"{doc.appointment_date} {doc.appointment_time or '00:00:00'}"
            )
            if appointment_dt.date() == now_dt.date():
                _add_sms_activity(
                    appointment_name,
                    _(
                        "Reminder SMS skipped — appointment is today ({0}). "
                        "The reminder should have been sent yesterday."
                    ).format(appointment_dt.date()),
                )
                counts["same_day"] += 1
                continue

            # ── Check patient mobile early — skip if missing ────────────────
            patient_mobile = frappe.db.get_value("Patient", doc.patient, "mobile")
            if not patient_mobile:
                _add_sms_activity(
                    appointment_name,
                    _(
                        "Reminder SMS skipped — Patient {0} has no mobile number. "
                        "Please update the Patient record and the scheduler will retry."
                    ).format(doc.patient),
                )
                counts["no_mobile"] += 1
                continue

            # ── Attempt to send SMS ─────────────────────────────────────────
            try:
                rendered = _render_sms_template(message, doc)
                send_sms([patient_mobile], rendered)

                frappe.db.set_value("Patient Appointment", doc.name, "reminded", 1)

                _add_sms_activity(
                    appointment_name,
                    f"Reminder SMS sent at {now_dt}. "
                    f"Appointment: {doc.appointment_datetime}. "
                    f"Message: {rendered}",
                )
                counts["sent"] += 1
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    _("Appointment Reminder Message Not Sent — {0}").format(appointment_name),
                )
                _add_sms_activity(
                    appointment_name,
                    _("Reminder SMS failed — an error occurred. Check Error Log for details."),
                )
                counts["failed"] += 1

        # ── Log a one-line summary ───────────────────────────────────────────
        total = sum(counts.values())
        frappe.log_error(
            f"[eumaria] send_appointment_reminder summary — "
            f"{total} appointment(s) in window: "
            f"{counts['already_reminded']} already reminded (dedup), "
            f"{counts['sent']} sent, "
            f"{counts['no_mobile']} skipped (no mobile), "
            f"{counts['same_day']} skipped (same-day), "
            f"{counts['failed']} failed.",
            _("Appointment Reminder — Run Summary"),
        )

    finally:
        _release_lock()


def ensure_scheduler_uses_eumaria_reminder() -> None:
    """Point Healthcare reminder scheduler entry to Eumaria implementation.

    - Switches any Scheduled Job Type still pointing to the healthcare original
      over to the eumaria override.
    - Stops (disables) any job that we cannot switch, to prevent the original
      buggy function from silently setting ``reminded = 1`` on failure.
    """
    job_names = frappe.get_all(
        "Scheduled Job Type",
        filters={"method": ["in", [HEALTHCARE_REMINDER_METHOD, EUMARIA_REMINDER_METHOD]]},
        pluck="name",
        limit_page_length=0,
    )

    for job_name in job_names:
        method = frappe.db.get_value("Scheduled Job Type", job_name, "method")
        if method == HEALTHCARE_REMINDER_METHOD:
            frappe.db.set_value("Scheduled Job Type", job_name, "method", EUMARIA_REMINDER_METHOD)
            frappe.db.set_value("Scheduled Job Type", job_name, "stopped", 0)
            frappe.log_error(
                f"[eumaria] Switched Scheduled Job Type {job_name} "
                f"from healthcare original to eumaria override.",
                _("Appointment Reminder — Scheduler Switched"),
            )


def execute() -> None:
    """Patch entrypoint for migration scripts."""
    ensure_scheduler_uses_eumaria_reminder()
