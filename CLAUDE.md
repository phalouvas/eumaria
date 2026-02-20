# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**eumaria** is a Frappe/ERPNext application for physiotherapy clinic customizations. It extends the Healthcare module's Patient Appointment with group session management and Patient Assessment with canvas-based body map annotation.

## Development Environment

### Prerequisites
- Python >= 3.10
- Frappe >= 15.0
- ERPNext Healthcare module
- Bench CLI (Frappe development environment)

### Common Development Commands

**Installation & Setup:**
```bash
# Install the app in a bench environment
bench get-app https://github.com/phalouvas/eumaria --branch feature/group-patient-appointments
bench install-app eumaria
bench migrate
```

**Testing & Debugging:**
```bash
# Run site migrations
bench --site [site-name] migrate

# Test weekly clone job (manual execution of Sunday cron)
bench --site [site-name] execute eumaria.events.patient_appointment.clone_group_session_appointments

# Clear cache after JS changes
bench --site [site-name] clear-cache
```

**Code Quality:**
```bash
# Install pre-commit hooks
cd apps/eumaria
pre-commit install

# Run pre-commit manually
pre-commit run --all-files
```

## Architecture & Key Patterns

### Frappe Extension Patterns
This app follows Frappe's extension patterns:
1. **Custom Fields**: Defined in `eumaria/physiotherapy/custom_fields.py` and applied via `after_install`/`after_migrate` hooks
2. **Class Overrides**: Core doctype classes overridden via `override_doctype_class` in hooks.py
3. **Document Events**: Hooked via `doc_events` for validation and processing
4. **Scheduled Tasks**: Cron jobs defined in `scheduler_events`
5. **Frontend Controllers**: JavaScript files attached to doctypes via `doctype_js` and `doctype_calendar_js`

### Core Modules

1. **Physiotherapy Module** (`eumaria/physiotherapy/`):
   - Custom field definitions for Patient Appointment, Patient Assessment, and templates
   - Property setters for field defaults and visibility
   - Print format creation for body map annotations

2. **Overrides** (`eumaria/overrides/`):
   - `PatientAppointment` class override for SMS suppression and overlap validation
   - Allows practitioner concurrency for group sessions
   - Manual SMS sending via whitelist method

3. **Events** (`eumaria/events/`):
   - Group session reminder marking on validation
   - Weekly appointment cloning (runs every Sunday)
   - Business logic for group session management

4. **Frontend Enhancements** (`eumaria/public/js/`):
   - `patient_appointment.js`: SMS button and form enhancements
   - `patient_assessment.js`: Canvas-based body map annotation with color palette
   - `patient_appointment_calendar.js`: Calendar view fixes for v16
   - `filterarea_mobile_fix.js`: Global monkey patch for Frappe v16 mobile bug

### Key Integration Points

**With ERPNext Healthcare:**
- Extends `Patient Appointment` doctype with `is_group_session` flag
- Extends `Patient Assessment` with `annotated_body_map` field
- Uses Healthcare Settings for SMS configuration
- Integrates with Practitioner Availability

**With Frappe Core:**
- Uses Frappe's hook system (`after_install`, `after_migrate`, `doc_events`, `scheduler_events`)
- Leverages document events (`validate`, `after_insert`)
- Implements whitelist methods for API endpoints
- Uses property setters for field customization

## Development Workflow

### Adding New Custom Fields
1. Add field definition to `custom_fields` dict in `eumaria/physiotherapy/custom_fields.py`
2. Run `bench migrate` to apply changes
3. Fields are automatically applied via `after_migrate` hook

### Modifying Group Session Behavior
- SMS suppression logic: `eumaria/overrides/patient_appointment.py`
- Weekly cloning: `eumaria/events/patient_appointment.py`
- Overlap validation: `validate_overlaps()` method in override

### Extending Body Map Annotation
- Canvas implementation: `eumaria/public/js/patient_assessment.js`
- Color palette in toolbar HTML (6 colors: Black, Blue, Red, Yellow, Orange, Green)
- Canvas sizing: `maxWidth` (0.9) and `maxHeight` (0.85) multipliers
- File management: Existing files deleted before new upload

### Testing Key Features

**Group Sessions:**
1. Create Patient Appointment with `is_group_session=1`
2. Verify no confirmation SMS sent
3. Test weekly clone: `bench --site [site-name] execute eumaria.events.patient_appointment.clone_group_session_appointments`

**Body Map Annotation:**
1. Create Patient Assessment Template with `requires_body_map=1` and upload base image
2. Create Patient Assessment using template
3. Click "Annotate Body Map" button to open canvas
4. Draw with different colors, save, verify preview appears

## Code Conventions

**Python:**
- Uses Ruff for linting and formatting (line length: 110, tab indent)
- Configuration in `pyproject.toml`
- Specific rules enabled: F, E, W, I, UP, B, RUF

**JavaScript:**
- ESLint + Prettier for code quality
- Configuration in `.eslintrc`

**Pre-commit Hooks:**
- Automatically runs ruff, eslint, prettier, pyupgrade
- Configured in `.pre-commit-config.yaml`

## Important Files for Reference

1. **`eumaria/hooks.py`** - App configuration and hook registrations
2. **`eumaria/physiotherapy/custom_fields.py`** - Custom field definitions and property setters
3. **`eumaria/overrides/patient_appointment.py`** - Core behavior overrides
4. **`eumaria/public/js/patient_assessment.js`** - Canvas-based body map implementation
5. **`eumaria/events/patient_appointment.py`** - Business logic and scheduled jobs
6. **`.github/copilot-instructions.md`** - Detailed architectural documentation

## Known Issues & Solutions

**Frappe v16 Mobile FilterArea Bug:**
- Issue: `TypeError: Cannot read properties of undefined (reading 'hide')` on mobile
- Solution: Global monkey patch in `eumaria/public/js/filterarea_mobile_fix.js`
- Loaded via `app_include_js` in hooks.py
- Fixes all list/calendar views across all DocTypes

**Calendar Color Regression (v16):**
- Issue: Appointment Type colors not displaying on calendar
- Solution: Override in `patient_appointment_calendar.js` with explicit `color: "color"` mapping

## Migration & Deployment

**After Code Changes:**
```bash
bench --site [site-name] migrate
bench --site [site-name] clear-cache
```

**Custom Field Updates:**
- Changes to `custom_fields.py` require `bench migrate`
- Property setters applied during migration

**JavaScript Changes:**
- Clear cache after modifying JS files: `bench --site [site-name] clear-cache`
- Pre-commit hooks ensure code quality