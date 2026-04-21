from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from gettext_auto.config import (
	CONFIG_FILENAME,
	Config,
	DEFAULT_TEMPLATE,
	GIT_PLACEHOLDER,
	format_last_translator,
	load_config,
	resolve_author,
	search_paths,
	write_default_config,
)


def _write(path: Path, body: str) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(body, encoding="utf-8")


def test_search_paths_order(tmp_path):
	cwd = tmp_path / "proj"
	home = tmp_path / "home"
	paths = search_paths(cwd, home)
	assert paths == [
		cwd / CONFIG_FILENAME,
		cwd / ".claude" / CONFIG_FILENAME,
		home / ".claude" / CONFIG_FILENAME,
	]


def test_load_config_returns_defaults_when_no_file(tmp_path):
	cfg = load_config(tmp_path, home=tmp_path / "home")
	assert cfg == Config()
	assert cfg.author_name == GIT_PLACEHOLDER
	assert cfg.author_email == GIT_PLACEHOLDER
	assert cfg.mark_fuzzy is True
	assert cfg.context == ""
	assert cfg.language_team == ""
	assert cfg.report_bugs_to == ""
	assert cfg.source_path is None


def test_load_config_reads_all_fields(tmp_path):
	cwd = tmp_path / "proj"
	cwd.mkdir()
	_write(cwd / CONFIG_FILENAME, """
author_name = "Alice"
author_email = "alice@example.com"
mark_fuzzy = false
context = "A screen reader project"
language_team = "French <fr@example.com>"
report_bugs_to = "bugs@example.com"
""")
	cfg = load_config(cwd, home=tmp_path / "home")
	assert cfg.author_name == "Alice"
	assert cfg.author_email == "alice@example.com"
	assert cfg.mark_fuzzy is False
	assert cfg.context == "A screen reader project"
	assert cfg.language_team == "French <fr@example.com>"
	assert cfg.report_bugs_to == "bugs@example.com"
	assert cfg.source_path == cwd / CONFIG_FILENAME


def test_load_config_missing_keys_use_defaults(tmp_path):
	cwd = tmp_path / "proj"
	cwd.mkdir()
	_write(cwd / CONFIG_FILENAME, 'author_name = "Alice"\n')
	cfg = load_config(cwd, home=tmp_path / "home")
	assert cfg.author_name == "Alice"
	assert cfg.author_email == GIT_PLACEHOLDER
	assert cfg.mark_fuzzy is True


def test_load_config_local_wins_over_project_claude(tmp_path):
	cwd = tmp_path / "proj"
	cwd.mkdir()
	_write(cwd / CONFIG_FILENAME, 'author_name = "Local"\n')
	_write(cwd / ".claude" / CONFIG_FILENAME, 'author_name = "Claude-project"\n')
	cfg = load_config(cwd, home=tmp_path / "home")
	assert cfg.author_name == "Local"
	assert cfg.source_path == cwd / CONFIG_FILENAME


def test_load_config_project_claude_wins_over_home_claude(tmp_path):
	cwd = tmp_path / "proj"
	home = tmp_path / "home"
	cwd.mkdir()
	_write(cwd / ".claude" / CONFIG_FILENAME, 'author_name = "Claude-project"\n')
	_write(home / ".claude" / CONFIG_FILENAME, 'author_name = "Claude-home"\n')
	cfg = load_config(cwd, home=home)
	assert cfg.author_name == "Claude-project"
	assert cfg.source_path == cwd / ".claude" / CONFIG_FILENAME


def test_load_config_home_claude_used_when_others_absent(tmp_path):
	cwd = tmp_path / "proj"
	home = tmp_path / "home"
	cwd.mkdir()
	_write(home / ".claude" / CONFIG_FILENAME, 'author_name = "Claude-home"\n')
	cfg = load_config(cwd, home=home)
	assert cfg.author_name == "Claude-home"
	assert cfg.source_path == home / ".claude" / CONFIG_FILENAME


def test_load_config_does_not_merge(tmp_path):
	"""First file found wins entirely. Lower-precedence files are ignored."""
	cwd = tmp_path / "proj"
	home = tmp_path / "home"
	cwd.mkdir()
	_write(cwd / CONFIG_FILENAME, 'author_name = "Local"\n')
	_write(home / ".claude" / CONFIG_FILENAME, """
author_name = "Claude-home"
language_team = "German <de@example.com>"
""")
	cfg = load_config(cwd, home=home)
	assert cfg.author_name == "Local"
	# language_team from the home config must NOT leak in.
	assert cfg.language_team == ""


def test_load_config_ignores_unknown_keys(tmp_path):
	cwd = tmp_path / "proj"
	cwd.mkdir()
	_write(cwd / CONFIG_FILENAME, """
author_name = "Alice"
totally_unknown_option = "ignored"
""")
	cfg = load_config(cwd, home=tmp_path / "home")
	assert cfg.author_name == "Alice"


def test_resolve_author_substitutes_git_placeholder(tmp_path):
	cfg = Config()  # defaults: both fields are "{git}"
	with patch("gettext_auto.config._git_config_value") as m:
		m.side_effect = lambda cwd, key: {"user.name": "Git User", "user.email": "git@example.com"}[key]
		name, email = resolve_author(cfg, tmp_path)
	assert name == "Git User"
	assert email == "git@example.com"


def test_resolve_author_leaves_explicit_values_alone(tmp_path):
	cfg = Config(author_name="Alice", author_email="alice@example.com")
	with patch("gettext_auto.config._git_config_value") as m:
		name, email = resolve_author(cfg, tmp_path)
		m.assert_not_called()
	assert name == "Alice"
	assert email == "alice@example.com"


def test_resolve_author_mixed(tmp_path):
	cfg = Config(author_name="Alice", author_email=GIT_PLACEHOLDER)
	with patch("gettext_auto.config._git_config_value") as m:
		m.return_value = "git@example.com"
		name, email = resolve_author(cfg, tmp_path)
		m.assert_called_once_with(tmp_path, "user.email")
	assert name == "Alice"
	assert email == "git@example.com"


def test_resolve_author_returns_empty_when_git_unset(tmp_path):
	cfg = Config()
	with patch("gettext_auto.config._git_config_value", return_value=""):
		name, email = resolve_author(cfg, tmp_path)
	assert name == ""
	assert email == ""


def test_format_last_translator_both(tmp_path):
	assert format_last_translator("Alice", "alice@example.com") == "Alice <alice@example.com>"


def test_format_last_translator_name_only():
	assert format_last_translator("Alice", "") == "Alice"


def test_format_last_translator_email_only():
	assert format_last_translator("", "alice@example.com") == "alice@example.com"


def test_format_last_translator_both_empty():
	assert format_last_translator("", "") == ""


def test_write_default_config_creates_file(tmp_path):
	target = tmp_path / CONFIG_FILENAME
	write_default_config(target)
	assert target.read_text(encoding="utf-8") == DEFAULT_TEMPLATE


def test_write_default_config_creates_parent_dirs(tmp_path):
	target = tmp_path / "nested" / ".claude" / CONFIG_FILENAME
	write_default_config(target)
	assert target.is_file()


def test_write_default_config_refuses_existing(tmp_path):
	target = tmp_path / CONFIG_FILENAME
	target.write_text("existing", encoding="utf-8")
	with pytest.raises(FileExistsError):
		write_default_config(target)
	assert target.read_text(encoding="utf-8") == "existing"


def test_write_default_config_force_overwrites(tmp_path):
	target = tmp_path / CONFIG_FILENAME
	target.write_text("existing", encoding="utf-8")
	write_default_config(target, force=True)
	assert target.read_text(encoding="utf-8") == DEFAULT_TEMPLATE


def test_default_template_loads_as_default_config(tmp_path):
	"""A freshly written template (all keys commented) must produce defaults."""
	target = tmp_path / CONFIG_FILENAME
	write_default_config(target)
	cfg = load_config(tmp_path, home=tmp_path / "home")
	# source_path points to the template file, but all values should equal defaults.
	assert cfg.source_path == target
	defaults = Config()
	assert cfg.author_name == defaults.author_name
	assert cfg.author_email == defaults.author_email
	assert cfg.mark_fuzzy == defaults.mark_fuzzy
	assert cfg.context == defaults.context
	assert cfg.language_team == defaults.language_team
	assert cfg.report_bugs_to == defaults.report_bugs_to
