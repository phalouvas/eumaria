# Copyright (c) 2026, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

"""One-time patch: reset `reminded=1` on future appointments that are > 24 h away.

These appointments were incorrectly marked as reminded (likely by a previous
bug that set the flag during creation).  Resetting them to 0 ensures the
reminder scheduler can process them when their window arrives.

The 25-hour buffer accounts for the maximum 23-hour remind window plus a 2-hour
safety margin.
"""

import frappe
from frappe.utils import add_to_date, now_datetime


def execute():
    """Reset reminded=1 for appointments > 25 hours in the future."""
    cutoff = add_to_date(now_datetime(), hours=25)

    bad_appointments = frappe.db.get_all(
        "Patient Appointment",
        filters={
            "appointment_datetime": [">=", cutoff],
            "reminded": 1,
        },
        pluck="name",
    )

    if not bad_appointments:
        return

    for name in bad_appointments:
        frappe.db.set_value("Patient Appointment", name, "reminded", 0)

    print(
        f"[eumaria] reset_reminded_flag: Reset reminded=0 on "
        f"{len(bad_appointments)} future appointment(s)."
    )
