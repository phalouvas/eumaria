# Copyright (c) 2026, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

from eumaria.overrides.appointment_reminder_override import ensure_scheduler_uses_eumaria_reminder


def execute():
	"""Switch Healthcare appointment reminder scheduled method to Eumaria override."""
	ensure_scheduler_uses_eumaria_reminder()
