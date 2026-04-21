import shutil
import subprocess
from pathlib import Path


def _run(*args, cwd):
	return subprocess.run(
		["gettext-auto", *args], cwd=str(cwd),
		capture_output=True, text=True, check=False,
	)


def test_full_babel_cycle(tmp_path, fixtures_dir):
	# Start with no-gettext fixture, write a minimal standard layout by hand,
	# add a marked string, and run the extract -> init-po -> update-po -> compile cycle.
	proj = tmp_path / "py"
	shutil.copytree(fixtures_dir / "python-no-gettext", proj)
	(proj / "babel.cfg").write_text("[python: **.py]\n", encoding="utf-8")
	(proj / "locale").mkdir(exist_ok=True)
	(proj / "locale/messages.pot").write_text(
		'# Translations template.\n'
		'#\n'
		'msgid ""\n'
		'msgstr ""\n'
		'"Project-Id-Version: messages 0.1\\n"\n'
		'"Content-Type: text/plain; charset=UTF-8\\n"\n'
		'"Content-Transfer-Encoding: 8bit\\n"\n'
		'"Language: en\\n"\n',
		encoding="utf-8",
	)
	# Add a translatable string to the source.
	(proj / "app.py").write_text(
		"def greet(): return _('Hello')\n", encoding="utf-8"
	)

	r = _run("extract", cwd=proj)
	assert r.returncode == 0, r.stderr
	assert (proj / "locale/messages.pot").read_text(encoding="utf-8").find("Hello") != -1

	r = _run("init-po", "fr", cwd=proj)
	assert r.returncode == 0, r.stderr
	assert (proj / "locale/fr/LC_MESSAGES/messages.po").is_file()

	r = _run("update-po", cwd=proj)
	assert r.returncode == 0, r.stderr

	# Add a translation, then compile.
	po_path = proj / "locale/fr/LC_MESSAGES/messages.po"
	content = po_path.read_text(encoding="utf-8").replace('msgstr ""', 'msgstr "Bonjour"', 1)
	po_path.write_text(content, encoding="utf-8")

	r = _run("compile", cwd=proj)
	assert r.returncode == 0, r.stderr
	assert (proj / "locale/fr/LC_MESSAGES/messages.mo").is_file()


def test_extract_without_babel_cfg_fails_cleanly(tmp_path):
	# Empty project: no babel.cfg -> pybabel raises FileNotFoundError internally.
	proj = tmp_path / "empty"
	proj.mkdir()
	r = _run("extract", cwd=proj)
	assert r.returncode != 0
	# Must be a ClickException, not a Python traceback.
	assert "Traceback" not in r.stderr
	assert "Error:" in r.stderr or "extract failed" in r.stderr


def test_flat_layout_babel_cycle(tmp_path, fixtures_dir):
	# Copy the flat fixture, add a translatable string, run the cycle.
	proj = tmp_path / "py"
	shutil.copytree(fixtures_dir / "python-flat-layout", proj)

	# Write a babel.cfg so extract can run.
	(proj / "babel.cfg").write_text("[python: **.py]\n", encoding="utf-8")
	# Add a translatable string somewhere the extractor will find it.
	(proj / "app.py").write_text(
		"import gettext\n_ = gettext.gettext\n"
		"def greet(): return _('Hello')\n",
		encoding="utf-8",
	)

	# extract -> pot should land where the existing pot lives.
	r = _run("extract", cwd=proj)
	assert r.returncode == 0, r.stderr
	pot_text = (proj / "translations/messages.pot").read_text(encoding="utf-8")
	assert "Hello" in pot_text

	# init-po for a new language -> should produce translations/de.po (flat).
	r = _run("init-po", "de", cwd=proj)
	assert r.returncode == 0, r.stderr
	assert (proj / "translations/de.po").is_file()
	assert not (proj / "translations/de").exists()  # NOT standard layout

	# update-po should update the existing fr.po in place.
	r = _run("update-po", cwd=proj)
	assert r.returncode == 0, r.stderr

	# compile should produce .mo files next to each .po.
	r = _run("compile", cwd=proj)
	assert r.returncode == 0, r.stderr
	assert (proj / "translations/fr.mo").is_file()
	assert (proj / "translations/de.mo").is_file()
