import frappe

DEFAULT_LANGUAGE = "el"
ENGLISH_LANGUAGE = "en"
ENGLISH_PREFIX = "en/"
HOME_ROUTES = ("", "home", "index")


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


def update_website_context(context):
	"""Website context hook: set ``<html lang>`` from the route only.

	``frappe/templates/base.html`` renders ``<html lang="{{ boot.lang }}">`` and
	``boot.lang`` comes from ``frappe.local.lang``, i.e. ``System Settings >
	language``. That setting stays ``"en"`` by decision D-051 (changing it would
	also translate the desk UI), and ``Web Page`` has no language field, so the
	attribute is corrected here per request.

	Read-only: nothing is written to the database, only the render context.
	"""
	try:
		lang, _twin_route = resolve_language(_get_route())

		boot = context.get("boot")
		if not boot:
			return {}

		updated_boot = dict(boot)
		updated_boot["lang"] = lang
		return {"boot": updated_boot}
	except Exception:
		frappe.log_error(frappe.get_traceback(), "eumaria update_website_context")
		return {}


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
