"""Per-entry verification. No LLM calls or I/O."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

from babel.messages.pofile import read_po
from babel.messages.mofile import write_mo

_PRINTF_NAMED = re.compile(r"%\([^)]+\)[a-zA-Z]")
_PRINTF_BASIC = re.compile(r"(?<!%)%[-+0 #]?\d*(?:\.\d+)?[sdrifxXeEgGoc]")
_DOUBLE_PERCENT = re.compile(r"%%")
_BRACE = re.compile(r"\{[^{}]*\}")
_DOLLAR = re.compile(r"(?<![A-Za-z0-9_])\$[A-Za-z_][A-Za-z0-9_]*")
_TAG = re.compile(r"</?[a-zA-Z][a-zA-Z0-9]*(?:\s[^>]*)?/?>")


def _tokens(text: str) -> Counter:
	counts: Counter = Counter()
	for pat in (_PRINTF_NAMED, _PRINTF_BASIC, _BRACE, _DOLLAR, _TAG):
		for m in pat.finditer(text):
			counts[m.group(0)] += 1
	counts["__pct_pct__"] = len(_DOUBLE_PERCENT.findall(text))
	return counts


@dataclass
class VerifyResult:
	errors: list[str] = field(default_factory=list)


def _compare_tokens(msgid: str, msgstr: str) -> list[str]:
	errs: list[str] = []
	src = _tokens(msgid)
	dst = _tokens(msgstr)
	for tok, n in src.items():
		if dst.get(tok, 0) != n:
			label = "%%" if tok == "__pct_pct__" else tok
			errs.append(
				f"placeholder mismatch for {label!r}: msgid has {n}, msgstr has {dst.get(tok, 0)}"
			)
	for tok, n in dst.items():
		if tok not in src and n > 0:
			label = "%%" if tok == "__pct_pct__" else tok
			errs.append(f"unexpected token in msgstr: {label!r} (not in msgid)")
	return errs


def verify_entry(
	msgid: str,
	msgstr: str | None,
	msgid_plural: str | None = None,
	msgstr_plural: list[str] | None = None,
	nplurals: int | None = None,
) -> VerifyResult:
	errors: list[str] = []
	if msgid_plural is not None:
		expected = nplurals if nplurals is not None else 2
		plurals = msgstr_plural or []
		if len(plurals) != expected:
			errors.append(
				f"plural form count mismatch: expected {expected}, got {len(plurals)}"
			)
		for i, p in enumerate(plurals):
			source = msgid if i == 0 else msgid_plural
			errors.extend(
				f"[plural {i}] {e}" for e in _compare_tokens(source, p or "")
			)
	else:
		errors.extend(_compare_tokens(msgid, msgstr or ""))
	return VerifyResult(errors=errors)


def msgfmt_check(po_path: Path | str) -> list[str]:
	"""Compile via Babel. Any exception = structural warning."""
	warnings: list[str] = []
	try:
		with open(po_path, "rb") as f:
			catalog = read_po(f)
		buf = BytesIO()
		write_mo(buf, catalog)
	except Exception as e:
		warnings.append(f"msgfmt: {e}")
	return warnings
