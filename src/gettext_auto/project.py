"""Project state detection."""
from __future__ import annotations

import os
from pathlib import Path
from typing import TypedDict
import polib

from gettext_auto import nvda as nvda_mod


# Directory names skipped when searching for .po / .pot / .py files.
# These are either VCS metadata, virtualenvs, build outputs, or vendored
# dependencies, none of which should contribute to project detection.
EXCLUDE_DIRS: frozenset[str] = frozenset({
	".git", ".hg", ".svn",
	".venv", "venv",
	".tox", ".nox",
	"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
	"node_modules",
	"build", "dist", "target",
	"site-packages",
	"vendor", "third_party", "vcpkg",
})


class LayoutInfo(TypedDict):
	style: str       # "standard" | "flat"
	po_base: str     # dir where new .po files should live (relative to root)
	domain: str      # from .pot filename stem, else "messages"


class DetectResult(TypedDict):
	project_type: str
	source_lang: str | None
	source_lang_confidence: str  # "header" | "default"
	gettext_status: str          # "not-integrated" | "integrated"
	pot_path: str | None
	po_files: dict[str, str]
	layout: LayoutInfo
	nvda: nvda_mod.NvdaInfo | None


def _is_excluded(path: Path, search_root: Path) -> bool:
	try:
		rel_parts = path.relative_to(search_root).parts
	except ValueError:
		return True
	return any(part in EXCLUDE_DIRS for part in rel_parts)


def _walk(search_root: Path, pattern: str) -> list[Path]:
	"""rglob filtered by EXCLUDE_DIRS, sorted shallow-first then alphabetically.

	Ordering is deterministic across filesystems so the first match is predictable.
	"""
	matches = [p for p in search_root.rglob(pattern) if not _is_excluded(p, search_root)]
	return sorted(
		matches,
		key=lambda p: (len(p.relative_to(search_root).parts), str(p).lower()),
	)


def _detect_project_type(root: Path) -> str:
	for _dirpath, dirnames, filenames in os.walk(root):
		dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
		if any(f.endswith(".py") for f in filenames):
			return "python"
	return "unknown"


def _rel(p: Path, root: Path) -> str:
	return str(p.relative_to(root)).replace("\\", "/")


def _find_po_files(search_root: Path, project_root: Path) -> dict[str, str]:
	"""Two-pass walk: standard layout (LC_MESSAGES) wins over flat for the same lang."""
	po_files: dict[str, str] = {}
	candidates = _walk(search_root, "*.po")
	for po in candidates:
		if po.parent.name == "LC_MESSAGES":
			lang = po.parent.parent.name
			if lang and lang not in po_files:
				po_files[lang] = _rel(po, project_root)
	for po in candidates:
		if po.parent.name == "LC_MESSAGES":
			continue
		lang = po.stem
		if lang and lang not in po_files:
			po_files[lang] = _rel(po, project_root)
	return po_files


def _find_pot(search_root: Path) -> Path | None:
	candidates = _walk(search_root, "*.pot")
	return candidates[0] if candidates else None


def _source_lang_from_pot(pot: Path | None) -> tuple[str | None, str]:
	if pot is None:
		return (None, "default")
	try:
		f = polib.pofile(str(pot))
	except Exception:
		return (None, "default")
	lang = (f.metadata.get("Language") or "").strip() or None
	if lang:
		return (lang, "header")
	return ("en", "default")


def _infer_layout(root: Path, po_files: dict[str, str], pot_path: str | None) -> LayoutInfo:
	"""Infer the project's po/pot layout so we can mirror it."""
	domain = Path(pot_path).stem if pot_path else "messages"
	# Prefer standard if any existing .po sits under an LC_MESSAGES dir.
	for po_rel in po_files.values():
		if "LC_MESSAGES" in po_rel.split("/"):
			# po_rel looks like "<base>/<lang>/LC_MESSAGES/<domain>.po"
			po_abs = root / po_rel
			locale_root = po_abs.parent.parent.parent
			po_base = str(locale_root.relative_to(root)).replace("\\", "/")
			return {"style": "standard", "po_base": po_base, "domain": domain}
	# Flat: any .po file at <base>/<lang>.po.
	if po_files:
		first_rel = next(iter(po_files.values()))
		po_base = str((root / first_rel).parent.relative_to(root)).replace("\\", "/")
		return {"style": "flat", "po_base": po_base, "domain": domain}
	# No .po yet: base off the .pot's parent if we have one.
	if pot_path:
		pot_parent = (root / pot_path).parent
		po_base = str(pot_parent.relative_to(root)).replace("\\", "/")
		# A .pot sitting directly under a "locale" dir suggests the standard
		# layout, so init-po lands at locale/<lang>/LC_MESSAGES/.
		style = "standard" if pot_parent.name == "locale" else "flat"
		return {"style": style, "po_base": po_base, "domain": domain}
	# Neither: standard-layout default for greenfield projects.
	return {"style": "standard", "po_base": "locale", "domain": domain}


def detect(root: Path | str, po_root: Path | str | None = None) -> DetectResult:
	"""Detect project state.

	If `po_root` is given, .po/.pot discovery is restricted to that subtree.
	Paths in the result are always relative to `root` (the project root).
	"""
	root = Path(root).resolve()
	if po_root is not None:
		search_root = Path(po_root).resolve()
		if not search_root.is_relative_to(root):
			raise ValueError(
				f"po_root {str(po_root)!r} must be under root {str(root)!r}"
			)
	else:
		search_root = root
	project_type = _detect_project_type(root)
	po_files = _find_po_files(search_root, root)
	pot = _find_pot(search_root)
	source_lang, confidence = _source_lang_from_pot(pot)
	integrated = bool(pot or po_files)
	pot_rel = _rel(pot, root) if pot else None
	layout = _infer_layout(root, po_files, pot_rel)
	return {
		"project_type": project_type,
		"source_lang": source_lang,
		"source_lang_confidence": confidence,
		"gettext_status": "integrated" if integrated else "not-integrated",
		"pot_path": pot_rel,
		"po_files": po_files,
		"layout": layout,
		"nvda": nvda_mod.detect(root),
	}
