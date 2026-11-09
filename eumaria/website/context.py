import frappe

DEFAULT_LANGUAGE = "el"
ENGLISH_LANGUAGE = "en"
ENGLISH_PREFIX = "en/"
HOME_ROUTES = ("", "home", "index")

#: Canonical public origin. ``hreflang`` and ``og:locale`` must point at the
#: production URLs, never at the dev host (``http://127.0.0.1:8000``), otherwise
#: the pairs are invalid in the environment where they are actually crawled.
CANONICAL_SITE_URL = "https://eumariaphysio.com"

#: Open Graph locales. Facebook's list has ``el_GR``; ``el_CY`` does not exist.
OG_LOCALES = {DEFAULT_LANGUAGE: "el_GR", ENGLISH_LANGUAGE: "en_US"}

#: Labels printed by the language switcher.
LANGUAGE_LABELS = {DEFAULT_LANGUAGE: "EL", ENGLISH_LANGUAGE: "EN"}

#: English labels for the ``Website Settings`` link tables, keyed by the *route* the
#: database stores — never by the label. The database is the Greek source of truth
#: and its labels get edited over time (today the navbar mixes "Υπηρεσίες" with
#: "Home"), so a label-keyed table would silently stop matching after a content edit.
#: Routes not listed here keep their row untouched.
ENGLISH_ITEM_LABELS = {
	"": "Home",
	"home": "Home",
	"services": "Services",
	"about": "About",
	"contact": "Contact",
	"terms": "Terms & Conditions",
	"privacy-policy": "Privacy Policy",
}


def resolve_language(route: str | None) -> tuple[str, str]:
	"""Return ``(language, twin_route)`` for a website route.

	The site is Greek at the root and English under ``/en/``::

		"" / "home"      -> ("el", "en")
		"en"             -> ("en", "")
		"en/services"    -> ("en", "services")
		"services/bowen" -> ("el", "en/services/bowen")

	The twin route is what later issues need to emit hyperlinks (hreflang links,
	language switcher). It never has a leading slash.
	"""
	route = _normalise_route(route)

	if route == ENGLISH_LANGUAGE:
		return ENGLISH_LANGUAGE, ""
	if route.startswith(ENGLISH_PREFIX):
		return ENGLISH_LANGUAGE, route[len(ENGLISH_PREFIX) :]
	if route in HOME_ROUTES:
		return DEFAULT_LANGUAGE, ENGLISH_LANGUAGE
	return DEFAULT_LANGUAGE, f"{ENGLISH_PREFIX}{route}"


def page_url(route: str | None) -> str:
	"""Absolute canonical URL for a website route, e.g. ``https://…/en``.

	``home`` / ``""`` / ``index`` all resolve to the clean root ``https://…/``
	so ``/home`` never leaks into ``hreflang`` (it 301-redirects to ``/``).
	"""
	route = _canonical_route(route)
	return f"{CANONICAL_SITE_URL}/{route}" if route else f"{CANONICAL_SITE_URL}/"


def twin_url(route: str | None) -> str:
	"""Root-relative URL of the same page in the other language.

	``""`` / ``"home"`` -> ``/en``, ``"en"`` -> ``/``, ``"services"`` ->
	``/en/services``, ``"en/services"`` -> ``/services``. The root pair is the only
	one that is not the same route with an ``en/`` prefix, hence one helper shared by
	the navbar rewrite and the language switcher.
	"""
	_, twin_route = resolve_language(route)
	return f"/{twin_route}" if twin_route else "/"


# Global chrome from ``Website Settings`` (issue #68, part C) needs no override here.
# Verified against the dev site on 2026-11-09 — none of the remaining single-value
# chrome fields is language-bearing:
#
#   call_to_action / call_to_action_url  NULL   (no CTA button is rendered)
#   title_prefix                         NULL   (nothing to strip from <title>)
#   brand_html                           NULL   (the brand is ``banner_image``: a logo)
#   banner_html                          ""     (empty)
#   copyright                            "All rights reserved"  (language-neutral)
#   footer_powered                       "Powered by <a …>KAINOTOMO PH LTD</a>"
#                                        (language-neutral: company name only)
#   footer_address                       English already ("EUMARIA Physio Centre /
#                                        Thermopylon 3, Liopetri 5320, Cyprus / …")
#
# If one of them ever gains Greek text, rewrite it here from ``context`` (never from
# the database) and only for English routes, the same way as ``_localise_items()``.


def update_website_context(context):
	"""Website context hook: per-route language signals.

	``frappe/templates/base.html`` renders ``<html lang="{{ boot.lang }}">`` and
	``boot.lang`` comes from ``frappe.local.lang``, i.e. ``System Settings >
	language``. That setting stays ``"en"`` by decision D-051 (changing it would
	also translate the desk UI), and ``Web Page`` has no language field, so the
	attribute is corrected here per request.

	For the 26 published bilingual ``Web Page`` routes it also adds:

	* three ``<link rel="alternate">`` tags (``el``, ``en``, ``x-default``)
	  through ``context.head_include`` — ``rel="alternate"`` cannot be emitted
	  through ``context.metatags``, which only renders ``<meta>`` elements;
	* ``og:locale`` / ``og:locale:alternate`` in ``context.metatags``;
	* a corrected ``<meta name="language">``.

	On English routes only it also replaces the Greek chrome that ``Website
	Settings`` holds for the whole site — the navbar/footer link tables (labels and
	URLs) and the EL|EN language switcher. See ``_localise_items()`` and
	``_add_language_switcher()``.

	The hook runs for every ``BaseTemplatePage`` renderer (``/login``, doc pages,
	…), so the pair is emitted only when both pages exist and are published.
	Read-only: nothing is written to the database, only the render context.
	"""
	try:
		route = _get_route()
		lang, twin_route = resolve_language(route)

		if lang == ENGLISH_LANGUAGE:
			_localise_items(context, "top_bar_items")
			_localise_items(context, "footer_items")

		if _is_published_page(route) and _is_published_page(twin_route):
			_add_hreflang_links(context, route, twin_route, lang)
			_add_locale_metatags(context, lang)
			_add_language_switcher(context, route, lang)

		return _update_boot_language(context, lang)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "eumaria update_website_context")
		return {}


def _localise_items(context, key: str) -> None:
	"""Replace ``context[key]`` with deep copies carrying the English label and URL.

	``context[key]`` comes from ``frappe.client_cache.get_doc("Website Settings")``,
	i.e. the *same row objects* are reused by later requests. Mutating them in place
	would leak English labels into the next Greek render, so every row is copied
	(children included) and the copy is rewritten instead.
	"""
	items = context.get(key)
	if not items:
		return
	context[key] = [_english_item(item) for item in items]


def _english_item(item) -> dict:
	"""Copy of one ``Top Bar Item`` row translated for an English route."""
	# ``frappe._dict.__getattr__`` returns None for unknown keys, so ``hasattr()`` is
	# True for plain dicts too — probe for a *callable* ``as_dict`` instead.
	as_dict = getattr(item, "as_dict", None)
	row = frappe._dict(as_dict() if callable(as_dict) else dict(item))
	row["child_items"] = [_english_item(child) for child in item.get("child_items") or []]

	label = ENGLISH_ITEM_LABELS.get(_normalise_route(row.get("url")))
	if label:
		row["label"] = label
		row["url"] = twin_url(row.get("url"))
	return row


def _add_language_switcher(context, route: str, lang: str) -> None:
	"""Append the EL|EN switcher to ``top_bar_items``.

	One row, appended last, on the right: ``navbar_items.html`` renders right-hand
	items in order and ``Login`` comes from ``navbar_login.html`` afterwards, so the
	switcher lands immediately before it. The row is a marker (``is_lang_switcher``)
	rather than a label/url pair because the switcher is two elements — the current
	language as non-link text and the other language as a link — which the stock
	``<a class="nav-link">`` row cannot express (see the app's
	``templates/includes/navbar/navbar_items.html`` override).
	"""
	items = context.get("top_bar_items")
	if not items:
		return

	other_lang = ENGLISH_LANGUAGE if lang == DEFAULT_LANGUAGE else DEFAULT_LANGUAGE
	current = LANGUAGE_LABELS[lang]
	other = LANGUAGE_LABELS[other_lang]
	href = frappe.utils.escape_html(twin_url(route))
	markup = (
		'<li class="nav-item eumaria-lang-switcher" role="group" aria-label="Language">'
		f'<span class="nav-link active" aria-current="true">{current}</span>'
		f'<a class="nav-link" href="{href}" hreflang="{other_lang}" lang="{other_lang}">{other}</a>'
		"</li>"
	)
	context["top_bar_items"] = [
		*items,
		frappe._dict(label="", url="", right=1, is_lang_switcher=1, html=markup),
	]


def _add_hreflang_links(context, route: str, twin_route: str, lang: str) -> None:
	"""Append the self-referencing, mutual ``el`` / ``en`` / ``x-default`` pair."""
	if lang == ENGLISH_LANGUAGE:
		greek_route, english_route = twin_route, route
	else:
		greek_route, english_route = route, twin_route

	greek_url = page_url(greek_route)
	links = (
		("el", greek_url),
		("en", page_url(english_route)),
		# Greek is the primary language for the local audience.
		("x-default", greek_url),
	)
	head_include = "".join(
		f'<link rel="alternate" hreflang="{hreflang}" href="{url}">\n' for hreflang, url in links
	)
	context["head_include"] = (context.get("head_include") or "") + head_include


def _add_locale_metatags(context, lang: str) -> None:
	"""(Re)set ``og:locale``, ``og:locale:alternate`` and ``language``."""
	metatags = context.get("metatags")
	if metatags is None:
		return

	alternate_lang = ENGLISH_LANGUAGE if lang == DEFAULT_LANGUAGE else DEFAULT_LANGUAGE
	metatags["og:locale"] = OG_LOCALES[lang]
	metatags["og:locale:alternate"] = OG_LOCALES[alternate_lang]
	# Core derives this from frappe.local.lang, i.e. the visitor's
	# Accept-Language header, which contradicts <html lang> and the hreflang links.
	metatags["language"] = lang


def _update_boot_language(context, lang: str) -> dict:
	"""``<html lang>`` comes from ``boot.lang``, i.e. ``System Settings > language``."""
	boot = context.get("boot")
	if not boot:
		return {}

	updated_boot = dict(boot)
	updated_boot["lang"] = lang
	return {"boot": updated_boot}


def _is_published_page(route: str | None) -> bool:
	"""True when ``route`` is a published ``Web Page`` (the root is stored as ``home``)."""
	db_route = _canonical_route(route) or "home"
	return bool(frappe.db.exists("Web Page", {"route": db_route, "published": 1}))


def _canonical_route(route: str | None) -> str:
	"""Route as it appears in a URL: ``home`` / ``index`` collapse to ``""``."""
	route = _normalise_route(route)
	return "" if route in HOME_ROUTES else route


def _normalise_route(route: str | None) -> str:
	return (route or "").strip().strip("/")


def _get_route() -> str:
	"""Requested website path, e.g. ``services/bowen`` for ``/services/bowen``.

	``frappe.request.path`` is the URL that was requested. ``frappe.local.path``
	is only a fallback because it holds the *resolved* endpoint: ``/`` becomes the
	value of ``Website Settings > home_page`` (or ``login``/``me`` for users).
	"""
	request = getattr(frappe.local, "request", None)
	path = getattr(request, "path", None) if request else None
	if not path:
		path = getattr(frappe.local, "path", None)
	return path or ""
