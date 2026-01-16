# Copilot Instructions for `eumaria`

## Overview
**eumaria** is a Frappe/ERPNext app for physiotherapy clinic customizations. It extends the Healthcare module's Patient Appointment DocType to support group sessions with multiple attendees, automated batch invoicing, and SMS notifications for appointment rescheduling.

## Core Architecture

### Key DocTypes & Modules
- **Patient Appointment** (extended via `eumaria/physiotherapy/`):
  - Custom fields: `is_group_session` (checkbox), `attendees` (table of `Group Appointment Attendee`)
  - Group mode: when `is_group_session=1`, multiple patients attend one appointment
  - Single primary patient derived from first attendee for backward compatibility
  - Appointment titles auto-generate with attendee names for group sessions

- **Group Appointment Attendee** (custom child DocType):
  - Stores patient info for each group session attendee
  - Validates no duplicate patients per group session

### Data Flows
1. **Group Session Creation**:
   - Set `is_group_session=1` on Patient Appointment
   - Add patients to `attendees` table via `Group Appointment Attendee` rows
   - Validation in `validate_patient_appointment()` ensures ≥1 attendee and no duplicates

2. **Rescheduling + SMS**:
   - When `appointment_date` or `appointment_time` changes, `send_reschedule_sms_on_update()` fires
   - Pulls SMS template from `Healthcare Settings.appointment_confirmation_msg`
   - Uses `send_message()` from Healthcare app to dispatch SMS

3. **Batch Invoicing**:
   - `create_group_invoices(appointment_name)` creates individual Sales Invoices per attendee
   - Each invoice links to the original group appointment and patient
   - Prevents re-invoicing (checks `appointment.invoiced` flag)

## Key Files & Patterns

- **`eumaria/physiotherapy/custom_fields.py`**: Runs at `after_install` hook; uses `create_custom_fields()` to add `is_group_session` and `attendees` fields to Patient Appointment
- **`eumaria/physiotherapy/patient_appointment.py`**:
  - `validate_patient_appointment(doc, method=None)`: hooks to `validate` event, validates group session rules
  - `on_update_appointment(doc, method=None)`: hooks to `on_update`, updates titles and triggers SMS
  - `send_reschedule_sms_on_update(doc)`: checks `has_value_changed()` for date/time, sends SMS via Healthcare's `send_message()`
- **`eumaria/physiotherapy/billing.py`**: `create_group_invoices()` whitelist for batch invoice generation

## Developer Workflow

### Installation & Setup
```bash
cd /workspace/development/frappe-bench
bench get-app https://github.com/phalouvas/eumaria --branch feature/sms-notifications
bench install-app eumaria  # Runs after_install hook to add custom fields
```

### Testing & Debugging
```bash
# Run migrations (if any patches added)
bench --site eumariaphysio.localhost migrate

# Test group session creation locally in bench console or via API
# Create Patient Appointment with is_group_session=1 and attendees

# Check SMS logs
bench --site eumariaphysio.localhost execute frappe.client.get --args '[\"Email Queue\"]'
```

### Extending Functionality
- **New custom fields for Patient Appointment**: Add to `eumaria/physiotherapy/custom_fields.py` and update `after_install` hook
- **New SMS flows**: Add validation/update hooks in `patient_appointment.py` and use `send_message(doc, template)` from Healthcare
- **New invoicing logic**: Extend `create_group_invoices()` in `billing.py` or create new whitelist methods

## Code Conventions

- **Python**: Ruff configured (line length 110, tab indent); select rules F, E, W, I, UP, B, RUF with specific ignores in `pyproject.toml`
- **Frontend**: ESLint + Prettier for JS (see `.eslintrc`, `prettier` config)
- **Pre-commit**: Install via `cd apps/eumaria && pre-commit install`; runs ruff, eslint, prettier, pyupgrade on commit

## Integration Points

- **Healthcare Module**: Depends on `Patient`, `Patient Appointment`, `Sales Invoice`, Healthcare Settings for SMS templates
- **Frappe Core**: Uses hooks (`after_install`, doc events like `validate`, `on_update`), DocType events, whitelist methods
- **Database**: Custom fields stored in `tabCustom Field`; custom DocType records in `tabGroup Appointment Attendee`

## Common Tasks

- **Add SMS notification for a new event**: Create validation/event hook, use `send_message(doc, template)` from Healthcare
- **Modify group session validation rules**: Edit `validate_patient_appointment()` in `patient_appointment.py`
- **Extend invoice generation**: Add parameters to `create_group_invoices()` or create new methods in `billing.py`
- **Update appointment title logic**: Modify title generation in `on_update_appointment()`

## Testing Notes

- No automated tests shipped; use bench to exercise workflows:
  ```bash
  bench --site eumariaphysio.localhost execute eumaria.physiotherapy.billing.create_group_invoices --args '["AP-2024-00001"]'
  ```
- Group session validation runs on every Patient Appointment save; test with `is_group_session=1` and varying attendee counts
- SMS flow requires Healthcare Settings SMS template and valid patient mobile numbers
