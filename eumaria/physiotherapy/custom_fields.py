# Copyright (c) 2026, KAINOTOMO PH LTD and contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

def execute():
	"""Create custom fields used by Eumaria customizations."""

	custom_fields = {
		"Patient Appointment": [
			{
				"fieldname": "is_group_session",
				"label": "Is Group Session",
				"fieldtype": "Check",
				"insert_after": "appointment_type",
			},
			{
				"fieldname": "group_session_source",
				"label": "Group Session Source",
				"fieldtype": "Link",
				"options": "Patient Appointment",
				"read_only": 1,
				"hidden": 1,
				"no_copy": 1,
				"insert_after": "is_group_session",
			},
			{
				"fieldname": "use_gift_card",
				"label": "Use Gift Card",
				"fieldtype": "Check",
				"insert_after": "mode_of_payment",
				"depends_on": "eval:!doc.invoiced",
				"description": "Check to use gift card for payment",
			},
			{
				"fieldname": "selected_gift_card",
				"label": "Gift Card",
				"fieldtype": "Link",
				"options": "Eumaria Gift Card",
				"insert_after": "use_gift_card",
				"depends_on": "eval:doc.use_gift_card && !doc.invoiced",
				"mandatory_depends_on": "eval:doc.use_gift_card && !doc.invoiced",
				"description": "Select gift card for payment",
			},
			{
				"fieldname": "gift_card_balance",
				"label": "Gift Card Balance",
				"fieldtype": "Currency",
				"insert_after": "selected_gift_card",
				"read_only": 1,
				"depends_on": "eval:doc.use_gift_card",
				"description": "Remaining balance on selected gift card",
				"fetch_from": "selected_gift_card.remaining_amount",
				"fetch_if_empty": 0,
			},
			{
				"fieldname": "gift_card_allocated_amount",
				"label": "Gift Card Allocated Amount",
				"fieldtype": "Currency",
				"insert_after": "gift_card_balance",
				"hidden": 1,
				"read_only": 1,
				"no_copy": 1,
				"description": "Amount allocated from gift card",
			},
		],
		"Patient Assessment": [
			{
				"fieldname": "annotated_body_map",
				"label": "Annotated Body Map",
				"fieldtype": "Attach Image",
				"insert_after": "assessment_template",
			},
		],
		"Patient Assessment Template": [
			{
				"fieldname": "requires_body_map",
				"label": "Requires Body Map",
				"fieldtype": "Check",
				"insert_after": "assessment_description",
			},
			{
				"fieldname": "base_body_map",
				"label": "Base Body Map Image",
				"fieldtype": "Attach Image",
				"insert_after": "requires_body_map",
				"description": "Upload the base silhouette image for annotation",
			},
		],
	}

	create_custom_fields(custom_fields, update=True)

	# Add property setters for gift card field behavior
	set_gift_card_field_properties()
	# Make score field optional first (this also adds options to fix healthcare module bug)
	make_score_field_optional()
	# Now set comments in list view (this will trigger validation)
	set_comments_in_list_view()
	create_or_update_patient_assessment_print_format()
	create_or_update_therapy_type_print_format()
	create_or_update_therapy_plan_print_format()
	set_practitioner_ignore_user_permissions()

	set_default_patient_appointment_view()


def set_gift_card_field_properties():
	"""Configure field dependencies and mandatory conditions for gift card payment fields in Patient Appointment."""
	# Make mode_of_payment field depend on use_gift_card
	make_property_setter(
		"Patient Appointment",
		"mode_of_payment",
		"depends_on",
		"eval:!doc.use_gift_card && !doc.invoiced",
		"Text",
	)

	# Make mode_of_payment conditionally mandatory (only when not using gift card)
	make_property_setter(
		"Patient Appointment",
		"mode_of_payment",
		"mandatory_depends_on",
		"",
		"Text",
	)

	# Make paid_amount field depend on use_gift_card
	make_property_setter(
		"Patient Appointment",
		"paid_amount",
		"depends_on",
		"eval:!doc.use_gift_card && !doc.invoiced",
		"Text",
	)

	# Make paid_amount conditionally mandatory (only when not using gift card)
	make_property_setter(
		"Patient Appointment",
		"paid_amount",
		"mandatory_depends_on",
		"",
		"Text",
	)

	# Make billing_item field depend on use_gift_card
	make_property_setter(
		"Patient Appointment",
		"billing_item",
		"depends_on",
		"eval:!doc.use_gift_card && !doc.invoiced",
		"Text",
	)

	# Make billing_item conditionally mandatory (only when not using gift card)
	make_property_setter(
		"Patient Appointment",
		"billing_item",
		"mandatory_depends_on",
		"",
		"Text",
	)

def set_default_patient_appointment_view():
	"""Force Patient Appointment to open in Calendar view by default."""
	existing = frappe.db.exists(
		"Property Setter",
		{
			"doc_type": "Patient Appointment",
			"property": "default_view",
		},
	)

	if existing:
		current_value = frappe.db.get_value("Property Setter", existing, "value")
		if current_value != "Calendar":
			frappe.db.set_value("Property Setter", existing, "value", "Calendar")
		return

	make_property_setter(
		"Patient Appointment",
		None,
		"default_view",
		"Calendar",
		"Select",
		for_doctype=True,
	)


def set_practitioner_ignore_user_permissions():
	"""Ensure practitioners can see all appointments regardless of user permissions."""
	make_property_setter(
		"Patient Appointment",
		"practitioner",
		"ignore_user_permissions",
		1,
		"Check",
	)


def set_comments_in_list_view():
	"""Make comments field visible in list view for Patient Assessment Sheet."""
	make_property_setter(
		"Patient Assessment Sheet",
		"comments",
		"in_list_view",
		1,
		"Check",
	)


def make_score_field_optional():
	"""Make score field not required so users can save without filling all scores."""
	# First, ensure the Select field has options if it doesn't have any
	# This is a workaround for a bug in the healthcare module
	make_property_setter(
		"Patient Assessment Sheet",
		"score",
		"options",
		"1\n2\n3\n4\n5",
		"Text",
	)
	
	# Now make the field not required
	make_property_setter(
		"Patient Assessment Sheet",
		"score",
		"reqd",
		0,
		"Check",
	)


def create_or_update_patient_assessment_print_format():
	"""Ensure a print format exists with body map and descriptions."""
	name = "Patient Assessment Body Map"
	existing = frappe.db.exists("Print Format", name)
	html = """
	<h2>Patient Assessment</h2>
	<p><strong>Patient:</strong> {{ doc.patient }} | <strong>Practitioner:</strong> {{ doc.healthcare_practitioner }}</p>
	<p><strong>Datetime:</strong> {{ doc.assessment_datetime }}</p>
	{% if doc.assessment_description %}
	<h4>Description</h4>
	<p>{{ doc.assessment_description }}</p>
	{% endif %}
	{% if doc.annotated_body_map %}
	<h4>Body Map</h4>
	<img src="{{ doc.annotated_body_map }}" style="max-width:100%;height:auto;" />
	{% endif %}
	<h4>Assessment Sheet</h4>
	<table class="table table-bordered table-sm">
		<thead><tr><th>Parameter</th><th>Score</th><th>Time</th><th>Comments</th></tr></thead>
		<tbody>
		{% for row in doc.assessment_sheet %}
			<tr>
				<td>{{ row.parameter }}</td>
				<td>{{ row.score }}</td>
				<td>{{ row.time }}</td>
				<td>{{ row.comments }}</td>
			</tr>
		{% endfor %}
		</tbody>
	</table>
	"""
	if existing:
		pf = frappe.get_doc("Print Format", name)
		pf.doc_type = "Patient Assessment"
		pf.module = "Eumaria"
		pf.html = html
		pf.disabled = 0
		pf.save()
	else:
		frappe.get_doc(
			{
				"doctype": "Print Format",
				"doc_type": "Patient Assessment",
				"name": name,
				"module": "Eumaria",
				"html": html,
			}
		).insert(ignore_permissions=True)


def create_or_update_therapy_type_print_format():
	"""Create/update Therapy Type print with all linked exercise details and images."""
	name = "Therapy Type With Exercises"
	existing = frappe.db.exists("Print Format", name)
	html = """
	<h2>Therapy Type</h2>
	<table class="table table-bordered table-sm" style="margin-bottom: 16px;">
		<tr>
			<td><strong>Therapy Type</strong></td>
			<td>{{ doc.therapy_type or "" }}</td>
			<td><strong>Medical Department</strong></td>
			<td>{{ doc.medical_department or "" }}</td>
		</tr>
		<tr>
			<td><strong>Default Duration (Minutes)</strong></td>
			<td>{{ doc.default_duration or "" }}</td>
			<td><strong>Healthcare Service Unit</strong></td>
			<td>{{ doc.healthcare_service_unit or "" }}</td>
		</tr>
		<tr>
			<td><strong>Description</strong></td>
			<td colspan="3">{{ doc.description or "" }}</td>
		</tr>
	</table>

	<h4>Exercise Types</h4>
	{% if doc.exercises %}
	<table class="table table-bordered table-sm">
		<thead>
			<tr>
				<th style="width: 20%;">Exercise Type</th>
				<th style="width: 15%;">Difficulty Level</th>
				<th style="width: 12%;">Counts Target</th>
				<th style="width: 15%;">Assistance Level</th>
				<th style="width: 38%;">Instructions / Images</th>
			</tr>
		</thead>
		<tbody>
		{% for row in doc.exercises %}
			{% set exercise_doc = frappe.get_doc("Exercise Type", row.exercise_type) if row.exercise_type else None %}
			<tr>
				<td>{{ row.exercise_type or "" }}</td>
				<td>{{ row.difficulty_level or (exercise_doc.difficulty_level if exercise_doc else "") }}</td>
				<td>{{ row.counts_target or "" }}</td>
				<td>{{ row.assistance_level or "" }}</td>
				<td>
					{% if exercise_doc and exercise_doc.description %}
						<div style="margin-bottom: 6px;"><strong>Description:</strong> {{ exercise_doc.description }}</div>
					{% endif %}

					{% if exercise_doc and exercise_doc.exercise_steps %}
						{% set instructions_path = exercise_doc.exercise_steps %}
						{% set lower_path = instructions_path|lower %}
						{% if lower_path.endswith('.png') or lower_path.endswith('.jpg') or lower_path.endswith('.jpeg') or lower_path.endswith('.gif') or lower_path.endswith('.bmp') or lower_path.endswith('.webp') %}
							<div style="margin-bottom: 6px;"><strong>Exercise Instructions:</strong></div>
							<img src="{{ instructions_path }}" style="max-width: 240px; max-height: 180px; height: auto; width: auto;" />
						{% else %}
							<div><strong>Exercise Instructions:</strong> <a href="{{ instructions_path }}" target="_blank">{{ instructions_path }}</a></div>
						{% endif %}
					{% endif %}

					{% if exercise_doc and exercise_doc.steps_table %}
						<div style="margin-top: 8px;"><strong>Exercise Steps:</strong></div>
						{% for step in exercise_doc.steps_table %}
							<div style="margin-top: 4px; padding: 6px; border: 1px solid #ddd;">
								{% if step.title %}<div><strong>{{ step.title }}</strong></div>{% endif %}
								{% if step.description %}<div>{{ step.description }}</div>{% endif %}
								{% if step.image %}
									<img src="{{ step.image }}" style="margin-top: 4px; max-width: 220px; max-height: 160px; height: auto; width: auto;" />
								{% endif %}
							</div>
						{% endfor %}
					{% endif %}
				</td>
			</tr>
		{% endfor %}
		</tbody>
	</table>
	{% else %}
	<p>No exercises configured.</p>
	{% endif %}
	"""

	_create_or_update_print_format(
		name=name,
		doc_type="Therapy Type",
		html=html,
		existing=existing,
	)


def create_or_update_therapy_plan_print_format():
	"""Create/update Therapy Plan print with therapy details and nested exercises."""
	name = "Therapy Plan Full"
	existing = frappe.db.exists("Print Format", name)
	html = """
	<h2>Therapy Plan</h2>
	<table class="table table-bordered table-sm" style="margin-bottom: 16px;">
		<tr>
			<td><strong>Plan</strong></td>
			<td>{{ doc.name }}</td>
			<td><strong>Patient</strong></td>
			<td>{{ doc.patient or "" }}</td>
		</tr>
		<tr>
			<td><strong>Start Date</strong></td>
			<td>{{ frappe.utils.formatdate(doc.start_date) if doc.start_date else "" }}</td>
			<td><strong>Status</strong></td>
			<td>{{ doc.status or "" }}</td>
		</tr>
		<tr>
			<td><strong>Company</strong></td>
			<td>{{ doc.company or "" }}</td>
			<td><strong>Template</strong></td>
			<td>{{ doc.therapy_plan_template or "" }}</td>
		</tr>
		<tr>
			<td><strong>Total Sessions</strong></td>
			<td>{{ doc.total_sessions or 0 }}</td>
			<td><strong>Sessions Completed</strong></td>
			<td>{{ doc.total_sessions_completed or 0 }}</td>
		</tr>
	</table>

	<h4>Therapy Types In Plan</h4>
	{% if doc.therapy_plan_details %}
	{% for detail in doc.therapy_plan_details %}
		<div style="margin-bottom: 14px;">
			<table class="table table-bordered table-sm" style="margin-bottom: 8px;">
				<tr>
					<td><strong>Therapy Type</strong></td>
					<td>{{ detail.therapy_type or "" }}</td>
					<td><strong>No Of Sessions</strong></td>
					<td>{{ detail.no_of_sessions or 0 }}</td>
				</tr>
				<tr>
					<td><strong>Interval</strong></td>
					<td>{{ detail.interval or "" }}</td>
					<td><strong>Sessions Completed</strong></td>
					<td>{{ detail.sessions_completed or 0 }}</td>
				</tr>
				<tr>
					<td><strong>Patient Care Type</strong></td>
					<td>{{ detail.patient_care_type or "" }}</td>
					<td><strong>Intent / Priority</strong></td>
					<td>{{ detail.intent or "" }}{% if detail.intent and detail.priority %} / {% endif %}{{ detail.priority or "" }}</td>
				</tr>
			</table>

			{% set therapy_type_doc = frappe.get_doc("Therapy Type", detail.therapy_type) if detail.therapy_type else None %}
			{% if therapy_type_doc and therapy_type_doc.exercises %}
				<table class="table table-bordered table-sm" style="margin-left: 10px; width: calc(100% - 10px);">
					<thead>
						<tr>
							<th style="width: 20%;">Exercise Type</th>
							<th style="width: 15%;">Difficulty Level</th>
							<th style="width: 12%;">Counts Target</th>
							<th style="width: 15%;">Assistance Level</th>
							<th style="width: 38%;">Instructions / Images</th>
						</tr>
					</thead>
					<tbody>
					{% for exercise_row in therapy_type_doc.exercises %}
						{% set exercise_doc = frappe.get_doc("Exercise Type", exercise_row.exercise_type) if exercise_row.exercise_type else None %}
						<tr>
							<td>{{ exercise_row.exercise_type or "" }}</td>
							<td>{{ exercise_row.difficulty_level or (exercise_doc.difficulty_level if exercise_doc else "") }}</td>
							<td>{{ exercise_row.counts_target or "" }}</td>
							<td>{{ exercise_row.assistance_level or "" }}</td>
							<td>
								{% if exercise_doc and exercise_doc.description %}
									<div style="margin-bottom: 6px;"><strong>Description:</strong> {{ exercise_doc.description }}</div>
								{% endif %}

								{% if exercise_doc and exercise_doc.exercise_steps %}
									{% set instructions_path = exercise_doc.exercise_steps %}
									{% set lower_path = instructions_path|lower %}
									{% if lower_path.endswith('.png') or lower_path.endswith('.jpg') or lower_path.endswith('.jpeg') or lower_path.endswith('.gif') or lower_path.endswith('.bmp') or lower_path.endswith('.webp') %}
										<div style="margin-bottom: 6px;"><strong>Exercise Instructions:</strong></div>
										<img src="{{ instructions_path }}" style="max-width: 240px; max-height: 180px; height: auto; width: auto;" />
									{% else %}
										<div><strong>Exercise Instructions:</strong> <a href="{{ instructions_path }}" target="_blank">{{ instructions_path }}</a></div>
									{% endif %}
								{% endif %}

								{% if exercise_doc and exercise_doc.steps_table %}
									<div style="margin-top: 8px;"><strong>Exercise Steps:</strong></div>
									{% for step in exercise_doc.steps_table %}
										<div style="margin-top: 4px; padding: 6px; border: 1px solid #ddd;">
											{% if step.title %}<div><strong>{{ step.title }}</strong></div>{% endif %}
											{% if step.description %}<div>{{ step.description }}</div>{% endif %}
											{% if step.image %}
												<img src="{{ step.image }}" style="margin-top: 4px; max-width: 220px; max-height: 160px; height: auto; width: auto;" />
											{% endif %}
										</div>
									{% endfor %}
								{% endif %}
							</td>
						</tr>
					{% endfor %}
					</tbody>
				</table>
			{% else %}
				<div style="margin-left: 10px;">No exercises configured for this therapy type.</div>
			{% endif %}
		</div>
	{% endfor %}
	{% else %}
	<p>No therapy types added to this plan.</p>
	{% endif %}
	"""

	_create_or_update_print_format(
		name=name,
		doc_type="Therapy Plan",
		html=html,
		existing=existing,
	)


def _create_or_update_print_format(name, doc_type, html, existing):
	"""Upsert helper for custom Jinja print formats."""
	if existing:
		pf = frappe.get_doc("Print Format", name)
		pf.doc_type = doc_type
		pf.module = "Eumaria"
		pf.custom_format = 1
		pf.print_format_type = "Jinja"
		pf.html = html
		pf.disabled = 0
		pf.save()
		return

	frappe.get_doc(
		{
			"doctype": "Print Format",
			"doc_type": doc_type,
			"name": name,
			"module": "Eumaria",
			"custom_format": 1,
			"print_format_type": "Jinja",
			"html": html,
		}
	).insert(ignore_permissions=True)
