"""Markdown and doc file translation.

Translates whole files declared via [[translate_files]] in the user config.
Source files matching the glob are read verbatim, handed to the model as
full-file content, and written back to the target path on apply. Existing
targets are skipped by default (translate-once semantics); pass force=True
to overwrite them.

Verification is structural, not semantic: the translated file must preserve
heading, code-fence, and link/image counts relative to the source, and must
not be empty. Prose correctness is the model's problem.
"""
from __future__ import annotations

import glob as _glob
import re
from pathlib import Path, PurePosixPath

from gettext_auto.config import TranslateFilesEntry
from gettext_auto import nvda as nvda_mod


def default_nvda_entries(info: nvda_mod.NvdaInfo) -> list[TranslateFilesEntry]:
	"""Built-in translate_files for NVDA add-ons when no user config is set."""
	root = info.get("addon_root") or ""
	prefix = f"{root}/" if root else ""
	return [TranslateFilesEntry(
		source=f"{prefix}doc/{{source}}/**/*.md",
		target=f"{prefix}doc/{{target}}/{{relpath}}",
	)]


def effective_entries(cfg_entries: list[TranslateFilesEntry], nvda_info: nvda_mod.NvdaInfo | None) -> list[TranslateFilesEntry]:
	"""User config wins. If the user set nothing and the project is an NVDA
	add-on, fall back to the NVDA default."""
	if cfg_entries:
		return list(cfg_entries)
	if nvda_info is not None:
		return default_nvda_entries(nvda_info)
	return []


def _expand(template: str, source_lang: str, target_lang: str, relpath: str = "") -> str:
	return (template
		.replace("{source}", source_lang)
		.replace("{target}", target_lang)
		.replace("{relpath}", relpath))


def _anchor(pattern: str) -> str:
	"""Literal prefix of a glob pattern, POSIX-separated, up to the first
	path segment containing a wildcard. Empty if the first segment already
	contains one."""
	parts = PurePosixPath(pattern).parts
	anchor_parts: list[str] = []
	for p in parts:
		if any(ch in p for ch in "*?["):
			break
		anchor_parts.append(p)
	return "/".join(anchor_parts)


def _compute_relpath(match_rel: str, source_pattern_expanded: str) -> str:
	anchor = _anchor(source_pattern_expanded)
	if not anchor:
		return match_rel
	if match_rel == anchor:
		return ""
	prefix = anchor + "/"
	if match_rel.startswith(prefix):
		return match_rel[len(prefix):]
	return match_rel


def _iter_matches(root: Path, pattern_expanded: str) -> list[str]:
	"""Return sorted POSIX-style relative paths of files matching the pattern
	under root. Uses glob.glob with recursive=True so ** works."""
	abs_pattern = (root / pattern_expanded).as_posix()
	matches = _glob.glob(abs_pattern, recursive=True)
	rels: list[str] = []
	for m in matches:
		p = Path(m)
		if not p.is_file():
			continue
		try:
			rel = p.resolve().relative_to(root.resolve()).as_posix()
		except ValueError:
			continue
		rels.append(rel)
	return sorted(set(rels))


def plan(
	root: Path,
	entries: list[TranslateFilesEntry],
	source_lang: str,
	target_lang: str,
) -> list[dict]:
	"""Compute every (source_path, target_path) pair for the given languages.
	First entry to claim a source path wins; later duplicates are dropped."""
	plans: list[dict] = []
	seen: set[str] = set()
	for entry in entries:
		src_expanded = _expand(entry.source, source_lang, target_lang)
		for match_rel in _iter_matches(root, src_expanded):
			if match_rel in seen:
				continue
			seen.add(match_rel)
			rp = _compute_relpath(match_rel, src_expanded)
			tgt_rel = _expand(entry.target, source_lang, target_lang, rp)
			plans.append({
				"source_path": match_rel,
				"target_path": tgt_rel,
			})
	return plans


def scan_files(
	root: Path,
	entries: list[TranslateFilesEntry],
	source_lang: str,
	target_lang: str,
	force: bool = False,
) -> dict:
	"""Return entries needing translation. Skips files whose target already
	exists unless force=True. Source file content is included inline."""
	plans = plan(root, entries, source_lang, target_lang)
	pending: list[dict] = []
	for p in plans:
		target_abs = root / p["target_path"]
		if not force and target_abs.exists():
			continue
		source_abs = root / p["source_path"]
		try:
			content = source_abs.read_text(encoding="utf-8")
		except (OSError, UnicodeDecodeError):
			continue
		pending.append({
			"id": p["source_path"],
			"source_path": p["source_path"],
			"target_path": p["target_path"],
			"content": content,
		})
	return {
		"project": {
			"source_lang": source_lang,
			"target_lang": target_lang,
		},
		"entries": pending,
	}


_FENCE_LINE_RE = re.compile(r"^\s*```")
_HEADING_RE = re.compile(r"^#{1,6}\s", re.MULTILINE)
_LINK_RE = re.compile(r"!?\[[^\]\n]*\]\([^)\n]*\)")


def _strip_fenced_code(text: str) -> str:
	"""Drop lines inside ``` fences. Fence lines themselves are dropped too;
	their count is tracked separately via count_fences."""
	out: list[str] = []
	in_fence = False
	for line in text.splitlines(keepends=True):
		if _FENCE_LINE_RE.match(line):
			in_fence = not in_fence
			continue
		if not in_fence:
			out.append(line)
	return "".join(out)


def _count_fences(text: str) -> int:
	"""Raw count of fence lines (lines starting with ```). A well-formed doc
	has an even count; comparing source-vs-target raw counts catches both
	mismatched block counts and malformed output (unclosed fence in target)."""
	return sum(1 for line in text.splitlines() if _FENCE_LINE_RE.match(line))


def count_structure(text: str) -> dict[str, int]:
	code_fences = _count_fences(text)
	stripped = _strip_fenced_code(text)
	headings = len(_HEADING_RE.findall(stripped))
	links = len(_LINK_RE.findall(stripped))
	return {"code_fences": code_fences, "headings": headings, "links": links}


def verify(source: str, translated: str) -> list[str]:
	"""Structural check. Returns a list of human-readable errors; empty = ok."""
	errors: list[str] = []
	if not translated or not translated.strip():
		errors.append("empty output")
		return errors
	src = count_structure(source)
	tgt = count_structure(translated)
	for key in ("code_fences", "headings", "links"):
		if src[key] != tgt[key]:
			errors.append(
				f"{key} count mismatch: source has {src[key]}, target has {tgt[key]}"
			)
	return errors


def apply_files(
	root: Path,
	entries: list[TranslateFilesEntry],
	source_lang: str,
	target_lang: str,
	translations: list[dict],
	force: bool = False,
) -> dict:
	"""Validate and write translated markdown. Accepts translations of the
	shape {"id": source_path, "content": translated_text}. Unknown ids and
	failed verification are reported; the target file is not written."""
	plans = plan(root, entries, source_lang, target_lang)
	by_id = {p["source_path"]: p for p in plans}
	out_entries: list[dict] = []
	summary = {"written_ok": 0, "verification_failed": 0, "skipped": 0}
	for tr in translations:
		eid = tr.get("id", "")
		content = tr.get("content", "")
		plan_entry = by_id.get(eid)
		if plan_entry is None:
			out_entries.append({
				"id": eid, "status": "final-fail",
				"errors": ["unknown id (not in current translate_files plan)"],
				"written": False,
			})
			summary["verification_failed"] += 1
			continue
		source_abs = root / plan_entry["source_path"]
		target_abs = root / plan_entry["target_path"]
		if target_abs.exists() and not force:
			out_entries.append({
				"id": eid, "status": "skipped",
				"errors": ["target exists (use --force to overwrite)"],
				"written": False,
				"target_path": plan_entry["target_path"],
			})
			summary["skipped"] += 1
			continue
		try:
			source_text = source_abs.read_text(encoding="utf-8")
		except Exception as e:
			out_entries.append({
				"id": eid, "status": "final-fail",
				"errors": [f"source read failed: {e}"],
				"written": False,
				"target_path": plan_entry["target_path"],
			})
			summary["verification_failed"] += 1
			continue
		errs = verify(source_text, content)
		if errs:
			out_entries.append({
				"id": eid, "status": "final-fail",
				"errors": errs, "written": False,
				"target_path": plan_entry["target_path"],
			})
			summary["verification_failed"] += 1
			continue
		target_abs.parent.mkdir(parents=True, exist_ok=True)
		target_abs.write_text(content, encoding="utf-8")
		out_entries.append({
			"id": eid, "status": "ok", "errors": [],
			"written": True,
			"target_path": plan_entry["target_path"],
		})
		summary["written_ok"] += 1
	return {"summary": summary, "entries": out_entries}
