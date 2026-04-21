import json
import subprocess


def _run(*args, cwd):
	result = subprocess.run(
		["gettext-auto", *args],
		cwd=str(cwd),
		capture_output=True,
		text=True,
		check=False,
	)
	return result


def test_detect_partial_fr(fixtures_dir):
	r = _run("detect", cwd=fixtures_dir / "python-partial-fr")
	assert r.returncode == 0, r.stderr
	data = json.loads(r.stdout)
	assert data["project_type"] == "python"
	assert data["gettext_status"] == "integrated"
	assert "fr" in data["po_files"]


def test_detect_no_gettext(fixtures_dir):
	r = _run("detect", cwd=fixtures_dir / "python-no-gettext")
	data = json.loads(r.stdout)
	assert data["scaffold_needed"] is True


def test_detect_cwd_flag(fixtures_dir, tmp_path):
	r = _run(
		"detect", "--cwd", str(fixtures_dir / "python-partial-fr"),
		cwd=tmp_path,
	)
	data = json.loads(r.stdout)
	assert data["gettext_status"] == "integrated"


def test_detect_flat_layout(fixtures_dir):
	r = _run("detect", cwd=fixtures_dir / "python-flat-layout")
	assert r.returncode == 0, r.stderr
	data = json.loads(r.stdout)
	assert "fr" in data["po_files"]


def test_detect_po_root_flag_scopes_discovery(tmp_path):
	header = (
		'msgid ""\nmsgstr ""\n'
		'"Content-Type: text/plain; charset=UTF-8\\n"\n'
		'"Language: fr\\n"\n\nmsgid "hi"\nmsgstr ""\n'
	)
	(tmp_path / "translations").mkdir()
	(tmp_path / "translations/fr.po").write_text(header, encoding="utf-8")
	(tmp_path / "unrelated/locale/de/LC_MESSAGES").mkdir(parents=True)
	(tmp_path / "unrelated/locale/de/LC_MESSAGES/messages.po").write_text(header, encoding="utf-8")

	r = _run("detect", "--po-root", "translations", cwd=tmp_path)
	assert r.returncode == 0, r.stderr
	data = json.loads(r.stdout)
	assert set(data["po_files"]) == {"fr"}


def test_detect_ignores_build_dir(tmp_path):
	header = (
		'msgid ""\nmsgstr ""\n'
		'"Content-Type: text/plain; charset=UTF-8\\n"\n'
		'"Language: fr\\n"\n\nmsgid "hi"\nmsgstr ""\n'
	)
	(tmp_path / "locale/fr/LC_MESSAGES").mkdir(parents=True)
	(tmp_path / "locale/fr/LC_MESSAGES/messages.po").write_text(header, encoding="utf-8")
	(tmp_path / "build/vendored/locale/de/LC_MESSAGES").mkdir(parents=True)
	(tmp_path / "build/vendored/locale/de/LC_MESSAGES/messages.po").write_text(header, encoding="utf-8")

	r = _run("detect", cwd=tmp_path)
	assert r.returncode == 0, r.stderr
	data = json.loads(r.stdout)
	assert set(data["po_files"]) == {"fr"}
