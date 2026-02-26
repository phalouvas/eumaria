# Eumaria AI Coding Instructions

## Project Overview
Eumaria is a Frappe app that extends ERPNext Healthcare with physiotherapy-specific customizations:
- **Group session management** for Patient Appointment (SMS suppression, weekly cloning)
- **Body map annotation** for Patient Assessment (canvas-based drawing, template-driven)
- **Gift card payment integration** with Payment Entry synchronization
- **Custom fields, overrides, and patches** to enhance core Healthcare functionality

This is a **monolithic Frappe app** that follows standard Frappe architecture: hooks, doctypes, custom scripts, and overrides.

## Key Architectural Patterns

### 1. Hooks Configuration (`eumaria/hooks.py`)
- **Override doctype classes**: `override_doctype_class` maps core doctypes to custom classes (e.g., `Patient Appointment` → `eumaria.overrides.patient_appointment.PatientAppointment`)
- **Document events**: `doc_events` hooks for `validate`, `on_cancel` etc. (e.g., mark group session reminders)
- **Scheduled tasks**: `scheduler_events` for cron jobs (weekly appointment cloning)
- **Whitelisted method overrides**: `override_whitelisted_methods` to replace core Healthcare methods (e.g., invoice creation)
- **Custom JS/CSS**: `app_include_css`, `doctype_js`, `doctype_calendar_js` inject frontend assets

### 2. Custom Fields & Property Setters
- Fields are defined in `eumaria/physiotherapy/custom_fields.py` and created via `create_custom_fields()`
- Executed automatically via `after_install` and `after_migrate` hooks
- **Example**: `is_group_session` (Check) inserted after `appointment_type` in Patient Appointment
- Property setters adjust field behavior (e.g., make score field optional, show comments in list view)

### 3. Doctype Overrides
- Extend core classes by subclassing (see `eumaria/overrides/patient_appointment.py`)
- **Pattern**: Import the original class, override methods (`validate`, `validate_overlaps`)
- Preserve core logic with `super()` calls where appropriate
- **Important**: Overrides must be registered in `hooks.py` (`override_doctype_class`)

### 4. Patches for Data Migrations
- Located in `eumaria/patches/`
- Each patch defines an `execute()` function that runs once during `bench migrate`
- **Example**: `remove_group_appointment_fields.py` deletes obsolete custom fields
- Use `frappe.db.exists`, `frappe.db.delete` with proper error logging

### 5. API Endpoints & Whitelisted Methods
- API modules reside in `eumaria/api/` (e.g., `gift_card.py`)
- Decorate with `@frappe.whitelist()` for web/desk accessibility
- **Pattern**: Return JSON‑serializable data; use `frappe.get_all`, `frappe.db.set_value`
- Integrate with Payment Entry: gift card balance mirrors `unallocated_amount`

### 6. Frontend JavaScript
- Custom scripts in `eumaria/public/js/`
- Attach to doctypes via `doctype_js` in hooks
- **Common patterns**: `frappe.ui.form.on('Doctype', { refresh(frm) { ... } })`
- Use `frappe.call` to invoke server methods with freeze UI

## Development Workflows

### Environment & Bench
- This is a **bench‑managed Frappe app**. Install via `bench get-app`, `bench install-app`
- Develop inside a bench directory; use `bench start` for local server
- **Testing**: `bench --site <sitename> execute eumaria.events.patient_appointment.clone_group_session_appointments`
- **Migration**: `bench migrate` applies patches and custom fields

### Code Quality & Pre‑commit
- Pre‑commit hooks enforce formatting and linting (`ruff`, `prettier`, `eslint`)
- **Run manually**: `pre-commit run --all-files`
- Configuration in `.pre-commit-config.yaml`; excludes node_modules, boilerplate
- **Ruff rules**: line‑length 110, Python 3.10 target, ignore certain flake8 codes

### Testing & Validation
- Unit tests are placed alongside doctypes (e.g., `test_eumaria_gift_card.py`)
- Use `frappe.get_doc`, `frappe.db.get_value` to verify data changes
- For manual testing, follow the steps in README.md (Patient Appointment cloning, body map annotation)

## Code Conventions

### Python
- Follow Frappe’s import order: standard library → third‑party → Frappe → local
- Use `frappe._()` for translatable strings
- **Error handling**: Log errors with `frappe.log_error()` and raise user‑friendly messages
- **Type hints**: Encourage but not enforced; use `-> float` etc. for clarity
- **Documentation**: Docstrings for public functions; include `Args`/`Returns` sections

### JavaScript
- Use `frappe.require` for dependencies (if needed)
- Prefer `const`/`let` over `var`
- Follow existing patterns for adding custom buttons (`frm.add_custom_button`)
- **Async calls**: Use `frappe.call` with freeze message for long operations

### File & Directory Naming
- Doctype folders: `eumaria/doctype/<doctype_name>/`
- Override modules: `eumaria/overrides/<doctype>.py`
- Event handlers: `eumaria/events/<doctype>.py`
- Patches: `eumaria/patches/<description>.py`
- API modules: `eumaria/api/<feature>.py`

## Integration Points

### Payment Entry Synchronization
- Gift cards create a linked Payment Entry on `after_insert`
- Remaining amount is kept in sync with `unallocated_amount` (see `sync_gift_card_remaining_amount`)
- On gift card submission/cancellation, the Payment Entry is submitted/cancelled

### SMS Suppression
- Group session appointments set `reminded = 1` during `validate`
- Override `validate` method to skip confirmation/reminder SMS
- Calendar events are still created via underlying Healthcare logic

### Weekly Appointment Cloning
- Cron job runs every Thursday (`0 0 * * 4`) via `scheduler_events`
- Clones last week’s flagged appointments forward 7 days
- Uses `group_session_source` Link field to avoid duplicate clones

### Body Map Annotation
- Canvas‑based drawing interface triggered from Patient Assessment
- Base image uploaded to Patient Assessment Template (`requires_body_map`, `base_body_map`)
- Annotated image stored as `annotated_body_map` attachment; single file per assessment

## Important Files & Directories
- `eumaria/hooks.py` – Central configuration
- `eumaria/physiotherapy/custom_fields.py` – Field definitions
- `eumaria/overrides/patient_appointment.py` – Core appointment logic
- `eumaria/events/patient_appointment.py` – Event handlers & cron job
- `eumaria/api/gift_card.py` – Gift card payment API
- `eumaria/doctype/eumaria_gift_card/` – Gift card doctype (controller, JSON, JS)
- `eumaria/public/js/patient_appointment.js` – Frontend extensions
- `eumaria/patches/` – One‑time data migrations

## Common Pitfalls
- **Missing hook registration**: Overrides won’t work unless added to `hooks.py`
- **Custom field collisions**: Ensure fieldnames are unique across apps
- **Patch idempotency**: Patches must be safe to run multiple times
- **Payment Entry state**: Always check `docstatus` before using `unallocated_amount`
- **Frontend dependencies**: JS/CSS must be listed in hooks to load on desk

## Quick Reference Commands
```bash
# Install app
bench get-app https://github.com/phalouvas/eumaria --branch develop
bench install-app eumaria
bench migrate

# Run pre‑commit checks
pre-commit run --all-files

# Manually test appointment cloning
bench --site <sitename> execute eumaria.events.patient_appointment.clone_group_session_appointments

# Check custom fields
bench --site <sitename> execute frappe.desk.form.load.getdocfield_metadata --doctype "Patient Appointment"
```