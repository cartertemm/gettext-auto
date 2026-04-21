import json
import subprocess


def _run(*args, cwd):
	return subprocess.run(
		["gettext-auto", *args], cwd=str(cwd),
		capture_output=True, text=True, check=False,
	)


def test_scan_returns_only_pending(fixtures_dir):
	r = _run("scan", "fr", cwd=fixtures_dir / "python-partial-fr")
	assert r.returncode == 0, r.stderr
	data = json.loads(r.stdout)
	assert data["project"]["source_lang"] == "en"
	assert data["project"]["target_lang"] == "fr"
	msgids = {e["msgid"] for e in data["entries"]}
	assert msgids == {"Close", "File", "Help"}
	assert "examples" in data


def test_scan_examples_drawn_from_existing(fixtures_dir):
	r = _run("scan", "fr", cwd=fixtures_dir / "python-partial-fr")
	data = json.loads(r.stdout)
	pairs = {(e["msgid"], e["msgstr"]) for e in data["examples"]}
	assert ("Save", "Enregistrer") in pairs
	assert ("Open", "Ouvrir") in pairs


def test_scan_batch_limits_entry_count(fixtures_dir):
	r = _run("scan", "fr", "--batch", "2", cwd=fixtures_dir / "python-partial-fr")
	data = json.loads(r.stdout)
	assert len(data["entries"]) <= 2


def test_scan_plurals_includes_plural_rule(fixtures_dir):
	r = _run("scan", "pl", cwd=fixtures_dir / "python-plurals")
	data = json.loads(r.stdout)
	assert "nplurals=3" in data["project"]["plural_rule"]
	assert data["entries"][0]["msgid_plural"] == "%d files"
