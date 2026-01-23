# Copilot Instructions for `eumaria`

## Overview
**eumaria** is a Frappe/ERPNext app for physiotherapy clinic customizations. It extends the Healthcare module's Patient Appointment with a group session flag that suppresses SMS confirmation/reminders and a weekly cloning job to copy flagged appointments from the previous week to the next.

## Core Architecture

### Key DocTypes & Modules
- **Patient Appointment** (extended via `eumaria`):
  - Custom fields: `is_group_session` (checkbox), `group_session_source` (hidden Link to Patient Appointment)
  - Behavior: when `is_group_session=1`, skip confirmation SMS and reminder SMS; eligible appointments clone weekly from last week’s schedule to the next week
  - `group_session_source` marks clones with their origin to prevent duplicates per source week

### Data Flows
1. **Group Session Creation**:
  - Set `is_group_session=1` on Patient Appointment
  - No attendees table; one Patient per appointment remains standard

2. **SMS Suppression**:
  - Confirmation SMS on insert is skipped when `is_group_session=1`
  - Reminder SMS is suppressed by marking `reminded=1` during validation for flagged records

3. **Weekly Cloning (Sundays)**:
  - Every Sunday, flagged appointments from the prior Mon–Sun are duplicated to the upcoming Mon–Sun at the same weekday/time
  - Copied fields: patient, appointment_type, company, practitioner/department/service_unit (per `appointment_for`), appointment_date/time (+7d), duration, notes, referring_practitioner, therapy_plan, therapy_type, procedure_template, add_video_conferencing, `is_group_session`
  - Excluded/system-regenerated: name, status, invoiced, paid_amount, billing_item, ref_sales_invoice, event/google_meet_link, position_in_queue, reference links; `mode_of_payment` is intentionally left empty on clones

## Key Files & Patterns

- **`eumaria/physiotherapy/custom_fields.py`**: Runs at `after_install` and `after_migrate`; adds `is_group_session` and `group_session_source` fields to Patient Appointment
- **`eumaria/overrides/patient_appointment.py`**: Overrides core Patient Appointment to skip confirmation SMS for flagged records and mark reminders as sent
- **`eumaria/events/patient_appointment.py`**:
  - `mark_group_session_reminded(doc, method=None)`: `validate` hook to set `reminded=1` for flagged records
  - `clone_group_session_appointments()`: scheduled job to clone last week’s flagged appointments into next week
- **`eumaria/eumaria/hooks.py`**: Declares `after_install`, `after_migrate`, `doc_events`, `scheduler_events`, and the override for Patient Appointment

## Developer Workflow

### Installation & Setup
```bash
cd /workspace/development/frappe-bench
bench get-app https://github.com/phalouvas/eumaria --branch feature/group-patient-appointments
bench install-app eumaria  # Adds custom fields via after_install
bench migrate               # Ensures fields via after_migrate and loads hooks
```

### Testing & Debugging
```bash
# Run migrations
bench --site eumariaphysio.localhost migrate

# Verify SMS suppression:
# Create a Patient Appointment with is_group_session=1; confirmation/reminder SMS should not send

# Dry-run weekly clone (manually execute the Sunday job):
bench --site eumariaphysio.localhost execute eumaria.events.patient_appointment.clone_group_session_appointments
```

### Extending Functionality
- **New custom fields for Patient Appointment**: Add to `eumaria/physiotherapy/custom_fields.py` and update hooks
- **SMS flows**: Use override + `validate` hook patterns shown to gate sends
- **Weekly duplication**: Extend the clone job or alter field whitelist in `eumaria/events/patient_appointment.py`

## Code Conventions

- **Python**: Ruff configured (line length 110, tab indent); select rules F, E, W, I, UP, B, RUF with specific ignores in `pyproject.toml`
- **Frontend**: ESLint + Prettier for JS (see `.eslintrc`, `prettier` config)
- **Pre-commit**: Install via `cd apps/eumaria && pre-commit install`; runs ruff, eslint, prettier, pyupgrade on commit

## Integration Points

- **Healthcare Module**: Depends on `Patient`, `Patient Appointment`, `Sales Invoice`, Healthcare Settings for SMS templates
- **Frappe Core**: Uses hooks (`after_install`, doc events like `validate`, `on_update`), DocType events, whitelist methods
- **Database**: Custom fields stored in `tabCustom Field`; clones tracked via `group_session_source`

## Common Tasks

- **Add SMS notification for a new event**: Use Healthcare `send_message()`; gate sends via override/validate hooks
- **Modify group session behavior**: Adjust clone whitelist or suppression logic in events/override files
- **Extend invoice generation**: Add new billing methods if needed (none shipped currently)
- **Update appointment title logic**: Modify via override if required

## Testing Notes

- No automated tests shipped; use bench to exercise workflows:
  ```bash
  # Weekly clone job (executes Sunday automatically; manual run for testing):
  bench --site eumariaphysio.localhost execute eumaria.events.patient_appointment.clone_group_session_appointments
  ```
- Group session suppression runs on every Patient Appointment save; test with `is_group_session=1`
- SMS flow depends on Healthcare Settings; suppression takes effect when the flag is set
