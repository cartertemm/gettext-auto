import json
import shutil
import subprocess
from pathlib import Path


def _run(*args, cwd, stdin=None):
	return subprocess.run(
		["gettext-auto", *args], cwd=str(cwd),
		input=stdin, capture_output=True, text=True, check=False,
	)


def test_end_to_end_translate_fr(tmp_path, fixtures_dir):
	proj = tmp_path / "py"
	shutil.copytree(fixtures_dir / "python-partial-fr", proj)

	r = _run("detect", cwd=proj)
	det = json.loads(r.stdout)
	assert det["gettext_status"] == "integrated"
	assert "fr" in det["po_files"]

	r = _run("scan", "fr", cwd=proj)
	scanned = json.loads(r.stdout)
	assert scanned["entries"]

	translations = {
		"Close": "Fermer",
		"File": "Fichier",
		"Help": "Aide",
	}
	payload = {
		"translations": [
			{"id": e["id"], "msgstr": translations[e["msgid"]]}
			for e in scanned["entries"]
		]
	}
	r = _run("apply", "fr", "--input", "-", cwd=proj, stdin=json.dumps(payload))
	result = json.loads(r.stdout)
	assert result["summary"]["written_ok"] == 3
	assert result["summary"]["verification_failed"] == 0
	assert result["summary"]["msgfmt_warnings"] == 0

	po_text = (proj / "locale/fr/LC_MESSAGES/messages.po").read_text(encoding="utf-8")
	for expected in ("Fermer", "Fichier", "Aide"):
		assert expected in po_text
	assert po_text.count("#, fuzzy") >= 3
