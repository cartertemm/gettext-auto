"""PO file operations. These are polib wrappers that never call the model."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
import polib


def load_po(path: Path | str) -> polib.POFile:
	return polib.pofile(str(path))


def entry_id(entry: polib.POEntry) -> str:
	key = f"{entry.msgctxt or ''}\x00{entry.msgid}"
	return hashlib.sha1(key.encode("utf-8")).hexdigest()


def enumerate_pending(pof: polib.POFile) -> list[polib.POEntry]:
	"""Return entries that still need translation: untranslated or fuzzy, excluding obsolete."""
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
	mark_fuzzy: bool = True,
) -> None:
	"""Write a translation. Raises ValueError if the entry is already translated and clean.

	By default, new translations are marked fuzzy so msgfmt won't compile them
	until a human reviews them. Pass mark_fuzzy=False only if you have another
	review step in place.
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
	if mark_fuzzy and "fuzzy" not in entry.flags:
		entry.flags.append("fuzzy")


def _utc_timestamp() -> str:
	return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M%z")


def update_po_headers(
	pof: polib.POFile,
	*,
	last_translator: str | None = None,
	language_team: str | None = None,
	report_bugs_to: str | None = None,
	revision_date: bool = False,
) -> None:
	"""Update PO metadata headers in place. Pass None or "" to leave a field unchanged."""
	if last_translator:
		pof.metadata["Last-Translator"] = last_translator
	if language_team:
		pof.metadata["Language-Team"] = language_team
	if report_bugs_to:
		pof.metadata["Report-Msgid-Bugs-To"] = report_bugs_to
	if revision_date:
		pof.metadata["PO-Revision-Date"] = _utc_timestamp()
