"""NVDA add-on manifest translation."""
from __future__ import annotations

from pathlib import Path
from typing import TypedDict


# Only these manifest keys are translated. Kept narrow on purpose; expanding
# the scope risks stomping non-prose fields (version, url, minimumNVDAVersion).
TRANSLATABLE_KEYS: tuple[str, ...] = ("summary", "description")


class NvdaInfo(TypedDict):
	addon_root: str          # "addon" or "" (flat layout)
	base_manifest_path: str  # relative to project root
	locale_base: str         # relative to project root


def detect(root: Path | str) -> NvdaInfo | None:
	"""Return NvdaInfo if this looks like an NVDA add-on, else None.

	Signal: either addon/manifest.ini exists, or manifest.ini at root sits
	alongside a locale/ directory.
	"""
	root = Path(root)
	if (root / "addon" / "manifest.ini").is_file():
		return {
			"addon_root": "addon",
			"base_manifest_path": "addon/manifest.ini",
			"locale_base": "addon/locale",
		}
	if (root / "manifest.ini").is_file() and (root / "locale").is_dir():
		return {
			"addon_root": "",
			"base_manifest_path": "manifest.ini",
			"locale_base": "locale",
		}
	return None


def _require_configobj():
	try:
		from configobj import ConfigObj
	except ImportError as e:
		raise RuntimeError(
			"configobj is required for NVDA manifest translation. "
			"Install with: pip install gettext-auto[nvda]"
		) from e
	return ConfigObj


def _load(path: Path):
	ConfigObj = _require_configobj()
	return ConfigObj(str(path), encoding="utf-8")


def _new_empty(path: Path):
	ConfigObj = _require_configobj()
	cfg = ConfigObj(encoding="utf-8")
	cfg.filename = str(path)
	return cfg


def _locale_path(root: Path, info: NvdaInfo, lang: str) -> tuple[str, Path]:
	rel = f"{info['locale_base']}/{lang}/manifest.ini"
	return rel, root / rel


def scan_manifest(root: Path | str, lang: str, info: NvdaInfo) -> dict:
	"""Enumerate keys in TRANSLATABLE_KEYS that have a source string but no
	translation yet. Emits the same entry shape as gettext `scan` so the model
	prompt and JSON contract can be reused.
	"""
	root = Path(root)
	base = _load(root / info["base_manifest_path"])
	locale_rel, locale_path = _locale_path(root, info, lang)
	current = _load(locale_path) if locale_path.is_file() else None
	entries: list[dict] = []
	for key in TRANSLATABLE_KEYS:
		source = base.get(key)
		if not source:
			continue
		existing = current.get(key, "") if current is not None else ""
		if existing:
			continue
		entries.append({
			"id": key,
			"msgid": source,
			"msgctxt": None,
			"msgid_plural": None,
			"extracted_comments": [],
			"references": [info["base_manifest_path"]],
			"current_msgstr": "",
			"current_flags": [],
			"status": "untranslated",
		})
	return {
		"project": {
			"source_lang": "en",
			"target_lang": lang,
			"plural_rule": "nplurals=2; plural=(n != 1);",
		},
		"entries": entries,
		"examples": [],
		"target_path": locale_rel,
	}


def apply_manifest(root: Path | str, lang: str, translations: list[dict], info: NvdaInfo) -> dict:
	"""Write translated values into the per-locale manifest. Creates the file
	if it doesn't exist. Only TRANSLATABLE_KEYS are accepted; unknown ids are
	reported as final-fail.
	"""
	root = Path(root)
	locale_rel, locale_path = _locale_path(root, info, lang)
	locale_path.parent.mkdir(parents=True, exist_ok=True)
	cfg = _load(locale_path) if locale_path.is_file() else _new_empty(locale_path)
	entries_out: list[dict] = []
	summary = {"written_ok": 0, "verification_failed": 0}
	for tr in translations:
		key = tr["id"]
		if key not in TRANSLATABLE_KEYS:
			entries_out.append({
				"id": key, "status": "final-fail",
				"errors": [f"unknown or non-translatable key: {key!r}"],
				"written": False,
			})
			summary["verification_failed"] += 1
			continue
		msgstr = tr.get("msgstr", "") or ""
		cfg[key] = msgstr
		entries_out.append({
			"id": key, "status": "ok", "errors": [], "written": True,
		})
		summary["written_ok"] += 1
	if summary["written_ok"] > 0:
		cfg.filename = str(locale_path)
		cfg.write()
	return {"summary": summary, "entries": entries_out, "target": locale_rel}
