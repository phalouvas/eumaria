### Eumaria

Eumaria Physio customizations for ERPNext and Frappe Healthcare. This app extends patient appointment management with support for group sessions, automated invoicing for group attendees, and SMS notifications for appointment rescheduling.

### Features

- **Group Session Support**: Create and manage group patient appointments with multiple attendees
- **Attendee Management**: Add multiple patients to a single appointment with automatic validation
- **Batch Invoicing**: Automatically generate individual Sales Invoices for all attendees in a group session
- **SMS Notifications**: Send SMS notifications to patients when appointments are rescheduled
- **Appointment Title Generation**: Automatically generate descriptive appointment titles with attendee names
- **Calendar Integration**: Update calendar events with group session details

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/phalouvas/eumaria --branch feature/sms-notifications
bench install-app eumaria
```

### Configuration

After installation, the app will automatically:
1. Add custom fields to Patient Appointment for group session support
2. Enable group session mode with attendees table
3. Configure SMS notification settings via Healthcare Settings

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
