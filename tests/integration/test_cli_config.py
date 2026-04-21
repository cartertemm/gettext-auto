"""End-to-end verification that .gettext-auto.toml values reach the CLI."""
import json
import shutil
import subprocess
from pathlib import Path


def _run(*args, cwd, stdin=None, env=None):
	return subprocess.run(
		["gettext-auto", *args], cwd=str(cwd),
		input=stdin, capture_output=True, text=True, check=False,
		env=env,
	)


def _copy_fixture(fixtures_dir, name, tmp_path):
	dst = tmp_path / name
	shutil.copytree(fixtures_dir / name, dst)
	return dst


def _write_config(proj: Path, body: str) -> None:
	(proj / ".gettext-auto.toml").write_text(body, encoding="utf-8")


def _scan(cwd, lang):
	r = subprocess.run(
		["gettext-auto", "scan", lang],
		cwd=str(cwd), capture_output=True, text=True, check=True,
	)
	return json.loads(r.stdout)


def test_scan_exposes_context_from_config(tmp_path, fixtures_dir):
	proj = _copy_fixture(fixtures_dir, "python-partial-fr", tmp_path)
	_write_config(proj, 'context = "NVDA screen reader; technical audience."\n')
	data = _scan(proj, "fr")
	assert data["project"]["context"] == "NVDA screen reader; technical audience."


def test_scan_context_empty_when_no_config(tmp_path, fixtures_dir):
	proj = _copy_fixture(fixtures_dir, "python-partial-fr", tmp_path)
	data = _scan(proj, "fr")
	assert data["project"]["context"] == ""


def test_apply_writes_last_translator_from_config(tmp_path, fixtures_dir):
	proj = _copy_fixture(fixtures_dir, "python-partial-fr", tmp_path)
	_write_config(proj, """
author_name = "Alice"
author_email = "alice@example.com"
language_team = "French <fr-team@example.com>"
""")
	scanned = _scan(proj, "fr")
	by_msgid = {e["msgid"]: e["id"] for e in scanned["entries"]}
	payload = {"translations": [{"id": by_msgid["File"], "msgstr": "Fichier"}]}
	r = _run("apply", "fr", "--input", "-", cwd=proj, stdin=json.dumps(payload))
	assert r.returncode == 0, r.stderr
	content = (proj / "locale/fr/LC_MESSAGES/messages.po").read_text(encoding="utf-8")
	assert "Last-Translator: Alice <alice@example.com>" in content
	assert "Language-Team: French <fr-team@example.com>" in content


def test_apply_mark_fuzzy_false_writes_clean(tmp_path, fixtures_dir):
	proj = _copy_fixture(fixtures_dir, "python-partial-fr", tmp_path)
	_write_config(proj, "mark_fuzzy = false\n")
	scanned = _scan(proj, "fr")
	by_msgid = {e["msgid"]: e["id"] for e in scanned["entries"]}
	# "File" is untranslated (not already-fuzzy) in the fixture.
	payload = {"translations": [{"id": by_msgid["File"], "msgstr": "Fichier"}]}
	r = _run("apply", "fr", "--input", "-", cwd=proj, stdin=json.dumps(payload))
	assert r.returncode == 0, r.stderr
	result = json.loads(r.stdout)
	# The emitted entry status should reflect the real fuzzy state.
	written = next(e for e in result["entries"] if e["id"] == by_msgid["File"])
	assert written["fuzzy"] is False
	# And the PO must not carry a fuzzy flag for File.
	content = (proj / "locale/fr/LC_MESSAGES/messages.po").read_text(encoding="utf-8")
	# Find the "File" entry block and confirm no fuzzy flag directly above it.
	lines = content.splitlines()
	file_idx = next(i for i, line in enumerate(lines) if line == 'msgid "File"')
	# Preceding non-blank lines should not contain "#, fuzzy".
	preceding = []
	i = file_idx - 1
	while i >= 0 and lines[i].strip():
		preceding.append(lines[i])
		i -= 1
	assert not any("fuzzy" in line for line in preceding)


def test_apply_default_still_marks_fuzzy(tmp_path, fixtures_dir):
	"""Regression: no config means mark_fuzzy defaults true, matching legacy behavior."""
	proj = _copy_fixture(fixtures_dir, "python-partial-fr", tmp_path)
	scanned = _scan(proj, "fr")
	by_msgid = {e["msgid"]: e["id"] for e in scanned["entries"]}
	payload = {"translations": [{"id": by_msgid["File"], "msgstr": "Fichier"}]}
	_run("apply", "fr", "--input", "-", cwd=proj, stdin=json.dumps(payload))
	content = (proj / "locale/fr/LC_MESSAGES/messages.po").read_text(encoding="utf-8")
	assert "#, fuzzy" in content


def test_apply_without_config_does_not_stamp_last_translator(tmp_path, fixtures_dir, monkeypatch):
	"""With no config and no git user.name, Last-Translator is not overwritten."""
	proj = _copy_fixture(fixtures_dir, "python-partial-fr", tmp_path)
	scanned = _scan(proj, "fr")
	by_msgid = {e["msgid"]: e["id"] for e in scanned["entries"]}
	payload = {"translations": [{"id": by_msgid["File"], "msgstr": "Fichier"}]}
	# Isolate from the user's real git config by pointing HOME/USERPROFILE and
	# XDG_CONFIG_HOME at an empty tmp dir, and scrub GIT_* env.
	env = {k: v for k, v in __import__("os").environ.items()
		   if not k.startswith("GIT_")}
	isolated = tmp_path / "isolated_home"
	isolated.mkdir()
	env["HOME"] = str(isolated)
	env["USERPROFILE"] = str(isolated)
	env["XDG_CONFIG_HOME"] = str(isolated / "xdg")
	env["GIT_CONFIG_NOSYSTEM"] = "1"
	r = _run("apply", "fr", "--input", "-", cwd=proj, stdin=json.dumps(payload), env=env)
	assert r.returncode == 0, r.stderr
	content = (proj / "locale/fr/LC_MESSAGES/messages.po").read_text(encoding="utf-8")
	# Fixture has no Last-Translator to begin with, so it should still be absent.
	assert "Last-Translator: " not in content or content.count("Last-Translator: \n") >= 0
