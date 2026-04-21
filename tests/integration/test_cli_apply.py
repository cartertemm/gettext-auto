import json
import shutil
import subprocess
from pathlib import Path


def _run(*args, cwd, stdin=None):
	return subprocess.run(
		["gettext-auto", *args], cwd=str(cwd),
		input=stdin, capture_output=True, text=True, check=False,
	)


def _copy_fixture(fixtures_dir, name, tmp_path):
	dst = tmp_path / name
	shutil.copytree(fixtures_dir / name, dst)
	return dst


def _scan(cwd, lang):
	r = subprocess.run(
		["gettext-auto", "scan", lang],
		cwd=str(cwd), capture_output=True, text=True, check=True,
	)
	return json.loads(r.stdout)


def test_apply_writes_fuzzy(tmp_path, fixtures_dir):
	proj = _copy_fixture(fixtures_dir, "python-partial-fr", tmp_path)
	scanned = _scan(proj, "fr")
	by_msgid = {e["msgid"]: e["id"] for e in scanned["entries"]}
	payload = {
		"translations": [
			{"id": by_msgid["File"], "msgstr": "Fichier"},
			{"id": by_msgid["Help"], "msgstr": "Aide"},
			{"id": by_msgid["Close"], "msgstr": "Fermer"},
		]
	}
	r = _run("apply", "fr", "--input", "-", cwd=proj, stdin=json.dumps(payload))
	assert r.returncode == 0, r.stderr
	result = json.loads(r.stdout)
	assert result["summary"]["written_ok"] == 3
	assert result["summary"]["verification_failed"] == 0
	content = (proj / "locale/fr/LC_MESSAGES/messages.po").read_text(encoding="utf-8")
	assert "Fichier" in content
	assert "#, fuzzy" in content


def test_apply_verification_failure_writes_autotrans_error(tmp_path, fixtures_dir):
	proj = _copy_fixture(fixtures_dir, "python-format-strings", tmp_path)
	scanned = _scan(proj, "fr")
	by_msgid = {e["msgid"]: e["id"] for e in scanned["entries"]}
	payload = {
		"translations": [
			{"id": by_msgid["Hello, %s!"], "msgstr": "Bonjour !"},
		]
	}
	r = _run("apply", "fr", "--input", "-", cwd=proj, stdin=json.dumps(payload))
	result = json.loads(r.stdout)
	assert result["summary"]["verification_failed"] == 1
	content = (proj / "locale/fr/LC_MESSAGES/messages.po").read_text(encoding="utf-8")
	assert "AUTOTRANS-ERROR" in content


def test_apply_plural_writes_all_forms(tmp_path, fixtures_dir):
	proj = _copy_fixture(fixtures_dir, "python-plurals", tmp_path)
	scanned = _scan(proj, "pl")
	eid = scanned["entries"][0]["id"]
	payload = {
		"translations": [{
			"id": eid,
			"msgstr_plural": ["%d plik", "%d pliki", "%d plikow"],
		}]
	}
	r = _run("apply", "pl", "--input", "-", cwd=proj, stdin=json.dumps(payload))
	assert r.returncode == 0, r.stderr
	result = json.loads(r.stdout)
	assert result["summary"]["written_ok"] == 1
	content = (proj / "locale/pl/LC_MESSAGES/messages.po").read_text(encoding="utf-8")
	assert "%d plik" in content
	assert "%d pliki" in content
	assert "%d plikow" in content


def test_apply_autotrans_error_does_not_accumulate(tmp_path, fixtures_dir):
	proj = _copy_fixture(fixtures_dir, "python-format-strings", tmp_path)
	scanned = _scan(proj, "fr")
	by_msgid = {e["msgid"]: e["id"] for e in scanned["entries"]}
	bad = {"translations": [{"id": by_msgid["Hello, %s!"], "msgstr": "Bonjour !"}]}

	# First bad apply
	_run("apply", "fr", "--input", "-", cwd=proj, stdin=json.dumps(bad))
	content1 = (proj / "locale/fr/LC_MESSAGES/messages.po").read_text(encoding="utf-8")
	assert content1.count("AUTOTRANS-ERROR:") == 1

	# Second apply with same bad translation
	_run("apply", "fr", "--input", "-", cwd=proj, stdin=json.dumps(bad))
	content2 = (proj / "locale/fr/LC_MESSAGES/messages.po").read_text(encoding="utf-8")
	assert content2.count("AUTOTRANS-ERROR:") == 1  # NOT 2


def test_apply_does_not_leave_tmp_file(tmp_path, fixtures_dir):
	proj = _copy_fixture(fixtures_dir, "python-partial-fr", tmp_path)
	scanned = _scan(proj, "fr")
	by_msgid = {e["msgid"]: e["id"] for e in scanned["entries"]}
	payload = {"translations": [{"id": by_msgid["File"], "msgstr": "Fichier"}]}
	_run("apply", "fr", "--input", "-", cwd=proj, stdin=json.dumps(payload))
	po_dir = proj / "locale/fr/LC_MESSAGES"
	assert not (po_dir / "messages.po.tmp").exists()


def test_apply_dry_run_does_not_write(tmp_path, fixtures_dir):
	proj = _copy_fixture(fixtures_dir, "python-partial-fr", tmp_path)
	scanned = _scan(proj, "fr")
	by_msgid = {e["msgid"]: e["id"] for e in scanned["entries"]}
	payload = {"translations": [{"id": by_msgid["File"], "msgstr": "Fichier"}]}
	before = (proj / "locale/fr/LC_MESSAGES/messages.po").read_bytes()
	r = _run("apply", "fr", "--input", "-", "--dry-run",
			 cwd=proj, stdin=json.dumps(payload))
	assert r.returncode == 0
	after = (proj / "locale/fr/LC_MESSAGES/messages.po").read_bytes()
	assert before == after
