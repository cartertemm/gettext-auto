"""User config loader for .gettext-auto.toml.

Checks three places in this order and uses whichever one turns up first:
  1. <cwd>/.gettext-auto.toml
  2. <cwd>/.claude/.gettext-auto.toml
  3. ~/.claude/.gettext-auto.toml

No file means defaults. author_name and author_email default to the literal
string "{git}", which gets expanded to `git config user.name` / `user.email`
on demand by resolve_author. The indirection is deliberate: a missing git
install, or one that's never been configured, shouldn't crash config loading.
It should just mean we skip those PO headers when we write.
"""
from __future__ import annotations

import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


CONFIG_FILENAME = ".gettext-auto.toml"
GIT_PLACEHOLDER = "{git}"


DEFAULT_TEMPLATE = """\
# gettext-auto config.
#
# Every key below is optional and commented out. Uncomment the ones
# you care about and leave the rest. Files are checked in this order,
# first match wins:
#   <cwd>/.gettext-auto.toml
#   <cwd>/.claude/.gettext-auto.toml
#   ~/.claude/.gettext-auto.toml

# Goes into the Last-Translator header of the .po files we write.
# "{git}" is a placeholder that reads `git config user.name` or
# `user.email` when we need it, so the git identity is the default.
# Set a literal string (a project email, a bot account, whatever)
# if you'd rather not be the one listed on AI output.
# author_name = "{git}"
# author_email = "{git}"

# true (the default): new translations land as fuzzy so msgfmt won't
# compile the .po until a human clears them. false: they land clean.
# Don't flip this off unless you have another review step.
# mark_fuzzy = true

# Short project description passed to the model. Makes a real difference
# on domain-specific work where the same word means different things in
# different contexts.
# context = "NVDA is a Windows screen reader; audience is blind developers."

# Standard .po header fields.
# language_team = "French <fr-team@example.com>"
# report_bugs_to = "bugs@example.com"

# Markdown / doc file translation. Each [[translate_files]] entry maps a
# glob of source files to a target path template. {source} and {target}
# get substituted with the language codes. {relpath} is the wildcard
# portion of the match, so a match at doc/en/guide/install.md against
# "doc/{source}/**/*.md" has {relpath} = "guide/install.md". Listing the
# entry below (uncommented) would mirror that into doc/<target>/guide/install.md.
# Existing target files are left alone; run `gettext-auto files scan <lang> --force`
# to regenerate.
#
# [[translate_files]]
# source = "doc/{source}/**/*.md"
# target = "doc/{target}/{relpath}"
"""


@dataclass
class TranslateFilesEntry:
	source: str
	target: str

	def validate(self) -> list[str]:
		"""Return a list of human-readable validation errors. Empty = valid."""
		errs: list[str] = []
		if not isinstance(self.source, str) or not self.source:
			errs.append("source must be a non-empty string")
		if not isinstance(self.target, str) or not self.target:
			errs.append("target must be a non-empty string")
		if isinstance(self.target, str) and "{target}" not in self.target:
			errs.append(f"target template must contain {{target}}: {self.target!r}")
		if isinstance(self.source, str) and isinstance(self.target, str):
			has_wildcards = any(ch in self.source for ch in "*?[")
			if "{relpath}" in self.target and not has_wildcards:
				errs.append(
					f"target references {{relpath}} but source {self.source!r} has no wildcards"
				)
		return errs


@dataclass
class Config:
	author_name: str = GIT_PLACEHOLDER
	author_email: str = GIT_PLACEHOLDER
	mark_fuzzy: bool = True
	context: str = ""
	language_team: str = ""
	report_bugs_to: str = ""
	translate_files: list[TranslateFilesEntry] = field(default_factory=list)
	source_path: Path | None = field(default=None, compare=False)


def search_paths(cwd: Path, home: Path) -> list[Path]:
	return [
		cwd / CONFIG_FILENAME,
		cwd / ".claude" / CONFIG_FILENAME,
		home / ".claude" / CONFIG_FILENAME,
	]


def load_config(cwd: Path, home: Path | None = None) -> Config:
	"""Return the first config found. Nothing merges.

	Unknown keys are dropped on the floor so adding options later doesn't
	break an older CLI reading a newer config file.
	"""
	if home is None:
		home = Path.home()
	defaults = Config()
	for path in search_paths(cwd, home):
		if not path.is_file():
			continue
		with path.open("rb") as f:
			data = tomllib.load(f)
		return Config(
			author_name=data.get("author_name", defaults.author_name),
			author_email=data.get("author_email", defaults.author_email),
			mark_fuzzy=data.get("mark_fuzzy", defaults.mark_fuzzy),
			context=data.get("context", defaults.context),
			language_team=data.get("language_team", defaults.language_team),
			report_bugs_to=data.get("report_bugs_to", defaults.report_bugs_to),
			translate_files=_parse_translate_files(data.get("translate_files", [])),
			source_path=path,
		)
	return Config()


def _parse_translate_files(raw: object) -> list[TranslateFilesEntry]:
	"""Parse the [[translate_files]] array-of-tables. Unknown keys are ignored."""
	if not isinstance(raw, list):
		return []
	entries: list[TranslateFilesEntry] = []
	for i, item in enumerate(raw):
		if not isinstance(item, dict):
			raise ValueError(f"translate_files[{i}] must be a table, got {type(item).__name__}")
		source = item.get("source", "")
		target = item.get("target", "")
		entry = TranslateFilesEntry(source=source, target=target)
		errs = entry.validate()
		if errs:
			raise ValueError(f"translate_files[{i}]: " + "; ".join(errs))
		entries.append(entry)
	return entries


def _git_config_value(cwd: Path, key: str) -> str:
	try:
		result = subprocess.run(
			["git", "config", "--get", key],
			cwd=str(cwd),
			capture_output=True,
			text=True,
			check=False,
		)
	except FileNotFoundError:
		return ""
	if result.returncode != 0:
		return ""
	return result.stdout.strip()


def resolve_author(cfg: Config, cwd: Path) -> tuple[str, str]:
	"""Expand the "{git}" placeholder by shelling out to `git config`.

	Either return value can come back empty (no git on the box, or the key
	isn't set). Callers should treat an empty string as "skip this header"
	rather than an error.
	"""
	name = cfg.author_name
	email = cfg.author_email
	if name == GIT_PLACEHOLDER:
		name = _git_config_value(cwd, "user.name")
	if email == GIT_PLACEHOLDER:
		email = _git_config_value(cwd, "user.email")
	return name, email


def write_default_config(path: Path, force: bool = False) -> None:
	"""Write the commented template at `path`.

	Bails out with FileExistsError if something's already there. Pass
	force=True to clobber it anyway.
	"""
	if path.exists() and not force:
		raise FileExistsError(str(path))
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(DEFAULT_TEMPLATE, encoding="utf-8")


def format_last_translator(name: str, email: str) -> str:
	"""Build a Last-Translator header value. Empty when both inputs are."""
	if not name and not email:
		return ""
	if name and email:
		return f"{name} <{email}>"
	return name or email
