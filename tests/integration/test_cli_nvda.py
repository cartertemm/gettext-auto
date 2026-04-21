import json
import shutil
import subprocess

import pytest


configobj = pytest.importorskip("configobj")


def _run(*args, cwd, stdin=None):
	return subprocess.run(
		["gettext-auto", *args], cwd=str(cwd),
		input=stdin, capture_output=True, text=True, check=False,
	)


def test_nvda_scan_returns_pending_entries(fixtures_dir, tmp_path):
	proj = tmp_path / "proj"
	shutil.copytree(fixtures_dir / "nvda-addon", proj)
	r = _run("nvda", "scan", "fr", cwd=proj)
	assert r.returncode == 0, r.stderr
	data = json.loads(r.stdout)
	assert {e["id"] for e in data["entries"]} == {"summary", "description"}


def test_nvda_apply_writes_manifest(fixtures_dir, tmp_path):
	proj = tmp_path / "proj"
	shutil.copytree(fixtures_dir / "nvda-addon", proj)
	payload = {
		"translations": [
			{"id": "summary", "msgstr": "Un module de test"},
			{"id": "description", "msgstr": "Description FR."},
		]
	}
	r = _run("nvda", "apply", "fr", "--input", "-",
			 cwd=proj, stdin=json.dumps(payload))
	assert r.returncode == 0, r.stderr
	result = json.loads(r.stdout)
	assert result["summary"]["written_ok"] == 2
	cfg = configobj.ConfigObj(
		str(proj / "addon/locale/fr/manifest.ini"), encoding="utf-8"
	)
	assert cfg["summary"] == "Un module de test"
	assert cfg["description"] == "Description FR."


def test_nvda_scan_errors_on_non_addon(tmp_path):
	(tmp_path / "app.py").write_text("", encoding="utf-8")
	r = _run("nvda", "scan", "fr", cwd=tmp_path)
	assert r.returncode != 0
	assert "not an NVDA add-on" in r.stderr


def test_detect_surfaces_nvda_info(fixtures_dir):
	r = _run("detect", cwd=fixtures_dir / "nvda-addon")
	assert r.returncode == 0, r.stderr
	data = json.loads(r.stdout)
	assert data["nvda"] is not None
	assert data["nvda"]["addon_root"] == "addon"
