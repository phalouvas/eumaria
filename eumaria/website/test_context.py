"""Tests for the website context hook (issues #61, #62, #68)."""

import unittest
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from eumaria.website import context


class TestTwinUrl(unittest.TestCase):
	"""``twin_url()`` — the one place that knows the root is a special case."""

	def test_root_points_at_english_root(self):
		for route in ("", "/", "home", "index"):
			self.assertEqual(context.twin_url(route), "/en")

	def test_english_root_points_at_greek_root(self):
		for route in ("en", "/en", "en/"):
			self.assertEqual(context.twin_url(route), "/")

	def test_english_route_strips_the_prefix(self):
		self.assertEqual(context.twin_url("en/services/bowen"), "/services/bowen")

	def test_greek_route_gets_the_prefix(self):
		self.assertEqual(context.twin_url("services/bowen"), "/en/services/bowen")
		self.assertEqual(context.twin_url("/about"), "/en/about")


class TestLocaliseItems(FrappeTestCase):
	"""Section A — the ``Website Settings`` link tables on English routes."""

	def setUp(self):
		self.rows = [
			frappe._dict(name="1rjoj7nm0m", label="Home", url="/", right=1),
			frappe._dict(name="sc5uanvj3q", label="Υπηρεσίες", url="services", right=1),
			frappe._dict(name="p42672sel3", label="About", url="about", right=1),
			frappe._dict(name="ur4a3au9qd", label="Contact Us", url="contact", right=1),
		]

	def test_labels_and_urls_are_english(self):
		ctx = {"top_bar_items": self.rows}
		context._localise_items(ctx, "top_bar_items")

		self.assertEqual(
			[(item.label, item.url) for item in ctx["top_bar_items"]],
			[
				("Home", "/en"),
				("Services", "/en/services"),
				("About", "/en/about"),
				("Contact", "/en/contact"),
			],
		)

	def test_footer_rows_use_the_same_mapping(self):
		rows = [
			frappe._dict(label="Όροι και Προϋποθέσεις", url="terms"),
			frappe._dict(label="Πολιτική Απορρήτου", url="privacy-policy"),
		]
		ctx = {"footer_items": rows}
		context._localise_items(ctx, "footer_items")

		self.assertEqual(
			[(item.label, item.url) for item in ctx["footer_items"]],
			[("Terms & Conditions", "/en/terms"), ("Privacy Policy", "/en/privacy-policy")],
		)

	def test_cached_rows_are_not_mutated(self):
		"""The source document is cached across requests: mutating it leaks state."""
		ctx = {"top_bar_items": self.rows}
		context._localise_items(ctx, "top_bar_items")

		self.assertEqual(self.rows[1].label, "Υπηρεσίες")
		self.assertEqual(self.rows[1].url, "services")
		self.assertNotIn("child_items", self.rows[1])

	def test_unknown_route_is_left_alone(self):
		rows = [frappe._dict(label="Ιστολόγιο", url="blog")]
		ctx = {"top_bar_items": rows}
		context._localise_items(ctx, "top_bar_items")

		self.assertEqual(ctx["top_bar_items"][0].label, "Ιστολόγιο")
		self.assertEqual(ctx["top_bar_items"][0].url, "blog")

	def test_child_items_are_copied(self):
		"""Dropdown children are deep-copied too; only mapped routes are rewritten."""
		rows = [
			frappe._dict(
				label="Υπηρεσίες",
				url="services",
				child_items=[frappe._dict(label="Bowen", url="services/bowen")],
			)
		]
		ctx = {"top_bar_items": rows}
		context._localise_items(ctx, "top_bar_items")

		self.assertEqual(ctx["top_bar_items"][0].label, "Services")
		child = ctx["top_bar_items"][0].child_items[0]
		self.assertEqual(child.url, "services/bowen")
		self.assertIsNot(child, rows[0].child_items[0])

	def test_missing_or_empty_table_is_noop(self):
		ctx = {"footer_items": []}
		context._localise_items(ctx, "footer_items")
		self.assertEqual(ctx["footer_items"], [])

		context._localise_items(ctx, "top_bar_items")
		self.assertNotIn("top_bar_items", ctx)


class TestUpdateWebsiteContext(FrappeTestCase):
	"""The hook end to end, with the request route and page lookups stubbed."""

	def _context(self):
		return frappe._dict(
			top_bar_items=[
				frappe._dict(label="Home", url="/", right=1),
				frappe._dict(label="Υπηρεσίες", url="services", right=1),
			],
			footer_items=[frappe._dict(label="Επικοινωνία", url="contact")],
			boot={"lang": "el"},
			metatags={},
		)

	def _update(self, route, published=True):
		ctx = self._context()
		with (
			patch.object(context, "_get_route", return_value=route),
			patch.object(context, "_is_published_page", return_value=published),
		):
			# The hook mutates the context in place and returns only the keys it
			# replaces; BaseTemplatePage merges the returned dict back in.
			ctx.update(context.update_website_context(ctx) or {})
		return ctx

	def test_english_route_is_fully_localised(self):
		ctx = self._update("en")

		self.assertEqual([item.label for item in ctx["top_bar_items"][:2]], ["Home", "Services"])
		self.assertEqual([item.url for item in ctx["top_bar_items"][:2]], ["/en", "/en/services"])
		self.assertEqual(ctx["footer_items"][0].label, "Contact")
		self.assertEqual(ctx["footer_items"][0].url, "/en/contact")
		self.assertEqual(ctx["boot"]["lang"], "en")

	def test_greek_route_keeps_the_database_label(self):
		ctx = self._update("services")

		self.assertEqual(ctx["top_bar_items"][1].label, "Υπηρεσίες")
		self.assertEqual(ctx["top_bar_items"][1].url, "services")
		self.assertEqual(ctx["boot"]["lang"], "el")

	def test_non_content_route_is_left_untouched(self):
		ctx = self._update("login", published=False)

		self.assertEqual(ctx["top_bar_items"][1].label, "Υπηρεσίες")
		self.assertEqual(ctx["boot"]["lang"], "el")

	def test_broken_hook_returns_context_unchanged(self):
		with (
			patch.object(context, "_get_route", return_value="en"),
			patch.object(context, "_localise_items", side_effect=Exception("boom")),
			patch.object(frappe, "log_error") as log_error,
		):
			self.assertEqual(context.update_website_context(self._context()), {})

		log_error.assert_called_once()
