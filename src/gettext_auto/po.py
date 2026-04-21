"""PO file operations. polib wrappers that never call the model."""
from __future__ import annotations

import hashlib
from pathlib import Path
import polib


def load_po(path: Path | str) -> polib.POFile:
	return polib.pofile(str(path))


def entry_id(entry: polib.POEntry) -> str:
	key = f"{entry.msgctxt or ''}\x00{entry.msgid}"
	return hashlib.sha1(key.encode("utf-8")).hexdigest()


def enumerate_pending(pof: polib.POFile) -> list[polib.POEntry]:
	"""Untranslated or fuzzy, but not obsolete.

	Note: polib exposes msgstr_plural as a dict of ints -> strings; an entry
	with all-empty plural forms still has a truthy dict, so check per-value.
	"""
	pending = []
	for entry in pof:
		if entry.obsolete:
			continue
		if "fuzzy" in entry.flags:
			pending.append(entry)
			continue
		if entry.msgid_plural:
			plurals = entry.msgstr_plural or {}
			if not plurals or any(not v for v in plurals.values()):
				pending.append(entry)
		else:
			if not entry.msgstr:
				pending.append(entry)
	return pending


def serialize_entry(entry: polib.POEntry) -> dict:
	return {
		"id": entry_id(entry),
		"msgid": entry.msgid,
		"msgctxt": entry.msgctxt,
		"msgid_plural": entry.msgid_plural or None,
		"extracted_comments": list(entry.comment.splitlines()) if entry.comment else [],
		"references": [f"{f}:{l}" for f, l in entry.occurrences],
		"current_msgstr": entry.msgstr or "",
		"current_flags": list(entry.flags),
		"status": "fuzzy" if "fuzzy" in entry.flags else "untranslated",
	}


def clean_translations(pof: polib.POFile, limit: int) -> list[dict]:
	result = []
	for entry in pof:
		if entry.obsolete:
			continue
		if "fuzzy" in entry.flags:
			continue
		if entry.msgstr:
			result.append({"msgid": entry.msgid, "msgstr": entry.msgstr})
			if len(result) >= limit:
				break
	return result


def plural_rule(pof: polib.POFile) -> str:
	return (pof.metadata.get("Plural-Forms") or "nplurals=2; plural=(n != 1);").strip()


def write_translation(
	entry: polib.POEntry,
	msgstr: str,
	msgstr_plural: list[str] | None = None,
) -> None:
	"""Write translation, always marking fuzzy. Refuses to overwrite a clean translation.

	Symmetric with enumerate_pending: a plural entry is "clean" only if ALL
	plural forms are non-empty. A half-translated plural is pending and may be
	overwritten.
	"""
	if entry.msgid_plural:
		plurals = entry.msgstr_plural or {}
		fully_translated_plural = bool(plurals) and all(v for v in plurals.values())
		is_clean_translated = "fuzzy" not in entry.flags and fully_translated_plural
	else:
		is_clean_translated = "fuzzy" not in entry.flags and bool(entry.msgstr)
	if is_clean_translated:
		raise ValueError(f"Refusing to overwrite clean translation for msgid={entry.msgid!r}")
	if msgstr_plural is not None:
		entry.msgstr_plural = {i: s for i, s in enumerate(msgstr_plural)}
	else:
		entry.msgstr = msgstr
	if "fuzzy" not in entry.flags:
		entry.flags.append("fuzzy")
