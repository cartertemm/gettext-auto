import pytest

from gettext_auto import nvda


configobj = pytest.importorskip("configobj")


def test_detect_addon_wrapper(fixtures_dir):
	info = nvda.detect(fixtures_dir / "nvda-addon")
	assert info is not None
	assert info["addon_root"] == "addon"
	assert info["base_manifest_path"] == "addon/manifest.ini"
	assert info["locale_base"] == "addon/locale"


def test_detect_flat_manifest(tmp_path):
	(tmp_path / "manifest.ini").write_text(
		'summary = "s"\ndescription = "d"\n', encoding="utf-8"
	)
	(tmp_path / "locale").mkdir()
	info = nvda.detect(tmp_path)
	assert info is not None
	assert info["addon_root"] == ""
	assert info["base_manifest_path"] == "manifest.ini"
	assert info["locale_base"] == "locale"


def test_detect_none_for_plain_project(tmp_path):
	(tmp_path / "app.py").write_text("", encoding="utf-8")
	assert nvda.detect(tmp_path) is None


def test_detect_none_when_manifest_without_locale_dir(tmp_path):
	"""manifest.ini at root without a locale/ sibling is not enough."""
	(tmp_path / "manifest.ini").write_text('summary = "s"\n', encoding="utf-8")
	assert nvda.detect(tmp_path) is None


def test_scan_returns_summary_and_description_pending(fixtures_dir, tmp_path):
	import shutil
	proj = tmp_path / "proj"
	shutil.copytree(fixtures_dir / "nvda-addon", proj)
	info = nvda.detect(proj)
	out = nvda.scan_manifest(proj, "fr", info)
	keys = [e["id"] for e in out["entries"]]
	assert set(keys) == {"summary", "description"}
	assert out["target_path"] == "addon/locale/fr/manifest.ini"
	# Source strings should match the base manifest.
	by_id = {e["id"]: e["msgid"] for e in out["entries"]}
	assert by_id["summary"] == "A test add-on"
	assert "longer description" in by_id["description"]


def test_scan_skips_already_translated(fixtures_dir, tmp_path):
	import shutil
	proj = tmp_path / "proj"
	shutil.copytree(fixtures_dir / "nvda-addon", proj)
	# Pre-fill summary.
	(proj / "addon/locale/fr/manifest.ini").write_text(
		'summary = "Un module"\ndescription = ""\n', encoding="utf-8"
	)
	info = nvda.detect(proj)
	out = nvda.scan_manifest(proj, "fr", info)
	keys = [e["id"] for e in out["entries"]]
	assert keys == ["description"]


def test_scan_for_missing_locale_creates_no_file(fixtures_dir, tmp_path):
	"""scan must not write anything; de/ doesn't exist yet."""
	import shutil
	proj = tmp_path / "proj"
	shutil.copytree(fixtures_dir / "nvda-addon", proj)
	info = nvda.detect(proj)
	out = nvda.scan_manifest(proj, "de", info)
	assert {e["id"] for e in out["entries"]} == {"summary", "description"}
	assert not (proj / "addon/locale/de").exists()


def test_apply_writes_translations(fixtures_dir, tmp_path):
	import shutil
	proj = tmp_path / "proj"
	shutil.copytree(fixtures_dir / "nvda-addon", proj)
	info = nvda.detect(proj)
	translations = [
		{"id": "summary", "msgstr": "Un module de test"},
		{"id": "description", "msgstr": "Une description plus longue."},
	]
	out = nvda.apply_manifest(proj, "fr", translations, info)
	assert out["summary"]["written_ok"] == 2
	assert out["summary"]["verification_failed"] == 0
	# Round-trip: re-read and assert values.
	cfg = configobj.ConfigObj(str(proj / "addon/locale/fr/manifest.ini"), encoding="utf-8")
	assert cfg["summary"] == "Un module de test"
	assert cfg["description"] == "Une description plus longue."


def test_apply_creates_missing_locale_file(fixtures_dir, tmp_path):
	import shutil
	proj = tmp_path / "proj"
	shutil.copytree(fixtures_dir / "nvda-addon", proj)
	info = nvda.detect(proj)
	translations = [{"id": "summary", "msgstr": "Ein Modul"}]
	out = nvda.apply_manifest(proj, "de", translations, info)
	de_path = proj / "addon/locale/de/manifest.ini"
	assert de_path.is_file()
	cfg = configobj.ConfigObj(str(de_path), encoding="utf-8")
	assert cfg["summary"] == "Ein Modul"
	# description was not translated; must not be written.
	assert "description" not in cfg


def test_apply_rejects_unknown_key(fixtures_dir, tmp_path):
	import shutil
	proj = tmp_path / "proj"
	shutil.copytree(fixtures_dir / "nvda-addon", proj)
	info = nvda.detect(proj)
	translations = [
		{"id": "author", "msgstr": "Should not be written"},
		{"id": "summary", "msgstr": "OK"},
	]
	out = nvda.apply_manifest(proj, "fr", translations, info)
	assert out["summary"]["written_ok"] == 1
	assert out["summary"]["verification_failed"] == 1
	cfg = configobj.ConfigObj(str(proj / "addon/locale/fr/manifest.ini"), encoding="utf-8")
	assert cfg.get("summary") == "OK"
	assert "author" not in cfg


def test_detect_included_in_project_detect(fixtures_dir):
	from gettext_auto import project
	result = project.detect(fixtures_dir / "nvda-addon")
	assert result["nvda"] is not None
	assert result["nvda"]["addon_root"] == "addon"


def test_detect_nvda_none_for_plain_fixtures(fixtures_dir):
	from gettext_auto import project
	result = project.detect(fixtures_dir / "python-partial-fr")
	assert result["nvda"] is None
