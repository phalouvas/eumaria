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
		],
		"Patient Assessment": [
			{
				"fieldname": "annotated_body_map",
				"label": "Annotated Body Map",
				"fieldtype": "Attach Image",
				"insert_after": "assessment_description",
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

	set_comments_in_list_view()
	make_score_field_optional()
	create_or_update_patient_assessment_print_format()

	set_default_patient_appointment_view()


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
	make_property_setter(
		"Patient Assessment Sheet",
		"score",
		"default",
		"1",
		"Text",
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
