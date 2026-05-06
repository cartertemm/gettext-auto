"""Config loader for .gettext-auto.toml.

Looks in three places in order and uses the first one that was found:
  1. <cwd>/.gettext-auto.toml
  2. <cwd>/.claude/.gettext-auto.toml
  3. ~/.claude/.gettext-auto.toml

If no file is found, defaults apply. author_name and author_email default to "{git}", which resolves to `git config user.name` / `user.email` when needed.
If git isn't installed or those keys aren't set, the PO headers are left out.
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
# https://github.com/cartertemm/gettext-auto/
#
# All keys are optional. Uncomment whatever you need. The first file found
# is applied, checked in this order:
#   <cwd>/.gettext-auto.toml
#   <cwd>/.claude/.gettext-auto.toml
#   ~/.claude/.gettext-auto.toml

# Name and email for the Last-Translator header in generated .po files.
# "{git}" reads from git config, so your git identity is used by default.
# Set a literal value if you'd rather list a bot account or project address.
# author_name = "{git}"
# author_email = "{git}"

# When true (the default), new translations are marked fuzzy so msgfmt
# won't compile them until a human reviews each one. Set to false only if
# you have another review process in place.
# mark_fuzzy = true

# Short description of the project, passed to the model as context. Helps
# a lot when the same word means different things in different domains.
# context = "NVDA is a Windows screen reader; audience is blind developers."

# Standard .po header fields.
# language_team = "French <fr-team@example.com>"
# report_bugs_to = "bugs@example.com"

# Translate markdown or other doc files. Each entry pairs a source glob with
# a target path template. {source} and {target} are replaced with language
# codes. {relpath} captures the wildcard portion of the match -- for a file
# at doc/en/guide/install.md matched by "doc/{source}/**/*.md", {relpath}
# is "guide/install.md". The example below mirrors each source file into
# doc/<lang>/<relpath>. Existing targets are left alone unless you run with
# --force.
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
	"""Return the first config file found. Nothing merges across files.

	Unknown keys are ignored, so a newer config file won't break an older CLI.
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
	"""Obtains a config value from the git installation."""
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
	"""Resolve the author name and email, expanding "{git}" by reading git config.
	Either value may be empty if git isn't installed or the key isn't set.
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

	Raises a FileExistsError if the target exists. Pass
	force=True to clobber it anyway.
	"""
	if path.exists() and not force:
		raise FileExistsError(str(path))
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(DEFAULT_TEMPLATE, encoding="utf-8")


def format_last_translator(name: str, email: str) -> str:
	"""Build the Last-Translator header value. Returns "" if both name and email are empty."""
	if not name and not email:
		return ""
	if name and email:
		return f"{name} <{email}>"
	return name or email
