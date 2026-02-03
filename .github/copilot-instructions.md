# Copilot Instructions for `eumaria`

## Overview
**eumaria** is a Frappe/ERPNext app for physiotherapy clinic customizations. It extends the Healthcare module's Patient Appointment with group session management and Patient Assessment with canvas-based body map annotation.

## Core Architecture

### Key DocTypes & Modules
- **Patient Appointment** (extended via `eumaria`):
  - Custom fields: `is_group_session` (checkbox), `group_session_source` (hidden Link to Patient Appointment)
  - Behavior: when `is_group_session=1`, skip confirmation SMS and reminder SMS; eligible appointments clone weekly from last week's schedule to the next week
  - `group_session_source` marks clones with their origin to prevent duplicates per source week
  - Calendar view enhancement: Color field from linked Appointment Type displays on calendar events (fixes ERPNext v16 regression where colors were ignored)

- **Patient Assessment** (extended via `eumaria`):
  - Custom field: `annotated_body_map` (Attach Image) - positioned after assessment template, read-only when empty, editable when populated
  - Client-side enhancement: Canvas-based drawing dialog with color palette + eraser, responsive viewport sizing, file replacement
  - Property setters: `score` field default set to 1; `comments` field visible in assessment sheet list view
  - Print format: "Patient Assessment Body Map" shows description, annotated image, and assessment sheet with comments

- **Patient Assessment Template** (extended via `eumaria`):
  - Custom fields: `requires_body_map` (checkbox), `base_body_map` (Attach Image)
  - When `requires_body_map=1`, Annotate/Edit Body Map button appears on Patient Assessment form

### Data Flows
1. **Group Session Creation**:
  - Set `is_group_session=1` on Patient Appointment
  - No attendees table; one Patient per appointment remains standard

2. **SMS Suppression**:
  - Confirmation SMS on insert is skipped when `is_group_session=1`
  - Reminder SMS is suppressed by marking `reminded=1` during validation for flagged records

3. **Weekly Cloning (Sundays)**:
  - Every Sunday, flagged appointments from the prior Mon–Sun are duplicated to the upcoming Mon–Sun at the same weekday/time
  - Copied fields: patient, appointment_type, company, practitioner, department, service_unit, appointment_date/time (+7d), duration, notes, referring_practitioner, therapy_plan, therapy_type, procedure_template, add_video_conferencing, `is_group_session`
  - Skips cancelled or submitted appointments and avoids duplicates via `group_session_source` + target date check

4. **Body Map Annotation**:
  - User selects Patient Assessment Template with `requires_body_map=1` and uploaded `base_body_map` image
  - "Annotate Body Map" button appears on the Patient Assessment form (changes to "Edit Body Map" when annotation exists)
  - Clicking button or preview thumbnail opens a large dialog with base image loaded
  - Canvas sizes to 90% viewport width, 85% height (dialog width 95vw), preserving base image aspect ratio (recommended 800×600 or 600×800 PNG)
  - User draws with selected color (6-color palette: Black, Blue, Red, Yellow, Orange, Green); can change colors mid-drawing; eraser tool available (toggle + E shortcut)
  - Clear button resets canvas to base image
  - Save uploads PNG to `annotated_body_map` field; existing file deleted first via frappe.client.get_list + frappe.client.delete to prevent duplicate File records; auto-save on dialog close if drawing exists
  - Preview thumbnail appears below field (clickable to reopen editor); field becomes editable to allow clearing via X button
  - Print format renders assessment description, annotated image, and assessment sheet with scores/comments

## Key Files & Patterns

- **`eumaria/physiotherapy/custom_fields.py`**: Runs at `after_install` and `after_migrate`; adds custom fields to Patient Appointment, Patient Assessment, Patient Assessment Template; creates property setters for score/comments fields; creates "Patient Assessment Body Map" print format; sets Patient Appointment default view to Calendar
  - `execute()`: Main entry point, creates all custom fields
  - `set_comments_in_list_view()`: Makes comments visible in Patient Assessment Sheet list view
  - `make_score_field_optional()`: Sets score field `default=1` in Patient Assessment Sheet
  - `create_or_update_patient_assessment_print_format()`: Creates/updates print format with body map and assessment sheet
  - `set_default_patient_appointment_view()`: Forces Calendar view for Patient Appointment

- **`eumaria/public/js/patient_appointment.js`**: Client-side enhancements for Patient Appointment form (SMS functionality only)

- **`eumaria/public/js/patient_appointment_calendar.js`**: Calendar view configuration override to display Appointment Type colors correctly (fixes v16 regression)
  - Overrides `frappe.views.calendar["Patient Appointment"]` with explicit `color: "color"` field mapping
  - Uses Healthcare app's standard `get_events` method which LEFT JOINs Appointment Type to fetch color
  - Colors display on calendar events; appointments without colors use Frappe default blue

- **`eumaria/public/js/patient_assessment.js`**: Client-side enhancements for Patient Assessment form
  - `refresh()`: Auto-fills assessment_datetime; toggles `annotated_body_map` read-only state; renders preview thumbnail; adds Annotate/Edit button
  - `show_body_map_dialog()`: Opens large frappe.ui.Dialog with responsive canvas; loads base/existing image; handles mouse/touch/stylus drawing with color palette + eraser
  - `attach_body_map()`: Deletes existing File record by file_url, uploads new PNG via frappe.client.attach_file (private)
  - Canvas: dialog width 95vw; canvas max 90vw × 85vh, dynamically sized preserving image aspect ratio, 6-color picker, Clear + Eraser tool, auto-save on close

- **`eumaria/overrides/patient_appointment.py`**: Overrides core Patient Appointment to skip confirmation SMS for flagged records and mark reminders as sent

- **`eumaria/events/patient_appointment.py`**:
  - `mark_group_session_reminded(doc, method=None)`: `validate` hook to set `reminded=1` for flagged records
  - `clone_group_session_appointments()`: scheduled job to clone last week's flagged appointments into next week

- **`eumaria/eumaria/hooks.py`**: Declares `after_install`, `after_migrate`, `doc_events`, `scheduler_events`, `doctype_js`, `doctype_calendar_js`, and the override for Patient Appointment

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
- **New custom fields for Patient Appointment/Assessment**: Add to `eumaria/physiotherapy/custom_fields.py` `custom_fields` dict; run `bench migrate` to apply
- **SMS flows**: Use override + `validate` hook patterns shown to gate sends
- **Weekly duplication**: Extend the clone job or alter field whitelist in `eumaria/events/patient_appointment.py`
- **Canvas drawing features**: Extend `patient_assessment.js` - add tools (eraser, line width picker, undo/redo), change canvas size calculation, add pen pressure support
- **Body map templates**: Recommended PNG 800×600 (landscape) or 600×800 (portrait), light gray outlines, transparent/white background
- **Print format customization**: Edit `create_or_update_patient_assessment_print_format()` HTML template in `custom_fields.py`

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
- **Add body map annotation to other DocTypes**: Copy pattern from `patient_assessment.js`; create template DocType with `base_image` field, add `annotated_image` field to target DocType, register doctype_js in hooks
- **Customize canvas colors**: Edit color palette array in `patient_assessment.js` toolbar HTML (data-color attributes and inline styles)
- **Change canvas size**: Adjust `maxWidth` and `maxHeight` multipliers in `resizeCanvasToViewport()` function (currently 0.9 and 0.85)
- **Add drawing tools**: Extend `draw()` function with additional canvas context methods (e.g., `ctx.lineWidth` for pen size, `ctx.globalCompositeOperation = 'destination-out'` for eraser)
- **Modify field positioning**: Update `insert_after` in `custom_fields.py` and run `bench migrate`

## Testing Notes

- No automated tests shipped; use bench to exercise workflows:
  ```bash
  # Weekly clone job (executes Sunday automatically; manual run for testing):
  bench --site eumariaphysio.localhost execute eumaria.events.patient_appointment.clone_group_session_appointments
  
  # Clear cache after JS changes:
  bench --site eumariaphysio.localhost clear-cache
  ```
- Group session suppression runs on every Patient Appointment save; test with `is_group_session=1`
- SMS flow depends on Healthcare Settings; suppression takes effect when the flag is set
- Body map annotation:
  - Create Patient Assessment Template with `requires_body_map=1` and uploaded `base_body_map` image
  - Create Patient Assessment using template; verify Annotate button appears
  - Test drawing with mouse/touch/stylus; change colors; use Clear button
  - Save and verify File record created; preview appears; field becomes editable
  - Reopen editor; verify existing annotation loads for editing
  - Save again; verify old File deleted and new one created (check Files list)
  - Test print format: verify annotated image and assessment sheet render correctly
  - Test on mobile/tablet: verify canvas resizes on device rotation (may require dialog close/reopen)
