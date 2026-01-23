### Eumaria

Eumaria Physio customizations for ERPNext and Frappe Healthcare. This app extends Patient Appointment with group session management and Patient Assessment with body map annotation capabilities.

### Features

#### Patient Appointment Customizations
- **Is Group Session flag**: Add `is_group_session` checkbox on Patient Appointment
- **SMS suppression**: Skip confirmation SMS on insert and reminder SMS for flagged appointments
- **Weekly cloning**: Every Sunday, duplicate last week's flagged appointments to the upcoming week at the same weekday/time
- **Source tracking**: Hidden `group_session_source` Link tracks the origin to avoid duplicate clones
- **Calendar integration**: Calendar events continue to be created/updated via the underlying Healthcare logic

#### Patient Assessment Body Map Annotation
- **Canvas-based annotation**: Fullscreen responsive drawing interface with touch/stylus/mouse support
- **Color palette**: 6-color picker (Black, Blue, Red, Yellow, Orange, Green) for multi-color annotations
- **Template-driven**: Upload base body map images to Patient Assessment Template; annotations layer on top
- **File management**: Single file per assessment; editing replaces existing annotation (no duplicate files)
- **Preview thumbnail**: Clickable inline preview shows current body map and opens editor
- **Score field customization**: Optional score field with default value 1; comments visible in list view
- **Print format**: Custom "Patient Assessment Body Map" format showing description, annotated image, and assessment sheet

### Installation

Install via the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/phalouvas/eumaria --branch feature/group-patient-appointments
bench install-app eumaria
bench migrate
```

### Configuration

After installation/migration, the app will automatically:
1. Add custom fields to Patient Appointment: `is_group_session` (Check) and hidden `group_session_source` (Link)
2. Override Patient Appointment to suppress confirmation SMS for flagged appointments and mark reminders as sent
3. Register a Sunday cron job that clones last week’s flagged appointments into next week
### Try It / Testing

```bash
# Run site migrations
bench --site eumariaphysio.localhost migrate

# Test Patient Appointment Group Sessions:
# Create a Patient Appointment with is_group_session=1
# Confirmation/reminder SMS should not send for this record

# Manually run the weekly clone (Sunday job) for testing
bench --site eumariaphysio.localhost execute eumaria.events.patient_appointment.clone_group_session_appointments

# Test Patient Assessment Body Map Annotation:
# 1. Create a Patient Assessment Template
# 2. Check "Requires Body Map" and upload a base body map image (800x600 PNG recommended)
# 3. Create a Patient Assessment using that template
# 4. Click "Annotate Body Map" button to open the drawing canvas
# 5. Draw with different colors, save, and verify the preview appears
# 6. Click preview image or "Edit Body Map" to continue editing
```

**Patient Appointment Cloning**: Copies patient, appointment_type, company, practitioner/department/service_unit (per `appointment_for`), appointment_date/time (+7d), duration, notes, referring_practitioner, therapy_plan, therapy_type, procedure_template, add_video_conferencing, and the flag. Leaves `mode_of_payment` empty and lets system fields (name, status, reminded, billing, event/meet, queue, references) regenerate.

**Body Map Annotation**: Canvas dynamically sizes to 90% viewport width and 85% height while preserving image aspect ratio. Supports portrait/landscape images. Recommended base image: 800×600 or 600×800 PNG with light outlines.

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/eumaria
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff (Python linting and formatting)
- eslint (JavaScript linting)
- prettier (Code formatting)
- pyupgrade (Python syntax upgrades)

### Requirements

- Python >= 3.10
- Frappe >= 15.0
- ERPNext Healthcare module

### License

MIT
