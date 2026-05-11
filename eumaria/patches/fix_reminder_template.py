# Copyright (c) 2026, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

"""One-time patch: fix the appointment reminder SMS template to include
the practitioner name.

The old template was missing `{{doc.practitioner}}`, making the message
grammatically incomplete: "Το ραντεβού σας με είναι στις ..."
"""

import frappe


DEFAULT_FIXED_MESSAGE = (
    "Γεια σας {{doc.patient}},\n"
    "Υπενθύμιση: Το ραντεβού σας με {{doc.practitioner}} "
    "είναι στις {{doc.appointment_datetime}} στο {{doc.company}}.\n"
    "Σας ευχαριστούμε."
)


def execute():
    """Update Healthcare Settings reminder message if it's the broken template."""
    current = frappe.db.get_single_value(
        "Healthcare Settings", "appointment_reminder_msg"
    )

    # Only update if the message looks like the old broken one (missing practitioner).
    if current and "με είναι" in current and "{{doc.practitioner}}" not in current:
        frappe.db.set_value(
            "Healthcare Settings",
            "Healthcare Settings",
            "appointment_reminder_msg",
            DEFAULT_FIXED_MESSAGE,
        )
        print("[eumaria] fix_reminder_template: Updated appointment_reminder_msg in Healthcare Settings.")
    else:
        print(
            "[eumaria] fix_reminder_template: No update needed. "
            "Template already contains practitioner or has been customised."
        )
