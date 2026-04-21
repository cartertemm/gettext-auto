"""User configuration loaded from .gettext-auto.toml.

Search order (first match wins, no merging):
  1. <cwd>/.gettext-auto.toml
  2. <cwd>/.claude/.gettext-auto.toml
  3. ~/.claude/.gettext-auto.toml

Values default to a Config with empty strings and mark_fuzzy=True. The
author_name/author_email fields default to the sentinel "{git}", which resolves
to `git config user.name` / `user.email` at use time via resolve_author().
"""
from __future__ import annotations

import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


CONFIG_FILENAME = ".gettext-auto.toml"
GIT_PLACEHOLDER = "{git}"


DEFAULT_TEMPLATE = """\
# gettext-auto configuration.
# All keys are optional; uncomment to override a default.
# First-match-wins across: <cwd>/.gettext-auto.toml,
# <cwd>/.claude/.gettext-auto.toml, ~/.claude/.gettext-auto.toml.

# Last-Translator identity written to PO headers.
# The sentinel "{git}" resolves at write time via:
#   `git config user.name`  /  `git config user.email`
# Replace with literal strings if you do not want your name on AI output.
# author_name = "{git}"
# author_email = "{git}"

# Mark AI-written entries as fuzzy so msgfmt and translation tools
# surface them for human review before shipping. Leave on unless you
# have another review gate in place.
# mark_fuzzy = true

# One-paragraph project description fed to the model during translation.
# Raises quality substantially for domain-specific projects.
# context = "NVDA is a Windows screen reader; audience is technical."

# PO header metadata.
# language_team = "French <fr-team@example.com>"
# report_bugs_to = "bugs@example.com"
"""


@dataclass
class Config:
	author_name: str = GIT_PLACEHOLDER
	author_email: str = GIT_PLACEHOLDER
	mark_fuzzy: bool = True
	context: str = ""
	language_team: str = ""
	report_bugs_to: str = ""
	source_path: Path | None = field(default=None, compare=False)


def search_paths(cwd: Path, home: Path) -> list[Path]:
	return [
		cwd / CONFIG_FILENAME,
		cwd / ".claude" / CONFIG_FILENAME,
		home / ".claude" / CONFIG_FILENAME,
	]


def load_config(cwd: Path, home: Path | None = None) -> Config:
	"""Return the first config found, or defaults if none exist.

	Unknown keys in the file are ignored. Missing keys fall back to defaults.
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
			source_path=path,
		)
	return Config()


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
	"""Substitute the {git} placeholder with local git config values.

	Returns (name, email). Either may be empty if git is unavailable or the
	relevant key is unset.
	"""
	name = cfg.author_name
	email = cfg.author_email
	if name == GIT_PLACEHOLDER:
		name = _git_config_value(cwd, "user.name")
	if email == GIT_PLACEHOLDER:
		email = _git_config_value(cwd, "user.email")
	return name, email


def write_default_config(path: Path, force: bool = False) -> None:
	"""Write a commented template to `path`. Refuses to overwrite unless force=True."""
	if path.exists() and not force:
		raise FileExistsError(str(path))
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(DEFAULT_TEMPLATE, encoding="utf-8")


def format_last_translator(name: str, email: str) -> str:
	"""Render a Last-Translator value. Empty string if both inputs are empty."""
	if not name and not email:
		return ""
	if name and email:
		return f"{name} <{email}>"
	return name or email
