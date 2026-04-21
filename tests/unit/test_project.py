import pytest

from gettext_auto.project import detect


def test_detects_python_no_gettext(fixtures_dir):
	result = detect(fixtures_dir / "python-no-gettext")
	assert result["project_type"] == "python"
	assert result["gettext_status"] == "not-integrated"
	assert result["scaffold_needed"] is True
	assert result["po_files"] == {}


def test_detects_partial_fr_integrated(fixtures_dir):
	result = detect(fixtures_dir / "python-partial-fr")
	assert result["project_type"] == "python"
	assert result["gettext_status"] == "integrated"
	assert result["source_lang"] == "en"
	assert result["source_lang_confidence"] in {"header", "default"}
	assert "fr" in result["po_files"]


def test_source_lang_from_po_header(fixtures_dir):
	result = detect(fixtures_dir / "python-plurals")
	assert result["project_type"] == "python"
	assert result["gettext_status"] == "integrated"
	assert "pl" in result["po_files"]


def test_detects_flat_layout(fixtures_dir):
	result = detect(fixtures_dir / "python-flat-layout")
	assert result["gettext_status"] == "integrated"
	assert "fr" in result["po_files"]
	assert result["po_files"]["fr"].endswith("fr.po")
	# Should NOT include any LC_MESSAGES segment
	assert "LC_MESSAGES" not in result["po_files"]["fr"]


def test_layout_standard_fixture(fixtures_dir):
	result = detect(fixtures_dir / "python-partial-fr")
	assert result["layout"]["style"] == "standard"
	assert result["layout"]["po_base"] == "locale"
	assert result["layout"]["domain"] == "messages"


def test_layout_flat_fixture(fixtures_dir):
	result = detect(fixtures_dir / "python-flat-layout")
	assert result["layout"]["style"] == "flat"
	assert result["layout"]["po_base"] == "translations"
	assert result["layout"]["domain"] == "messages"


_POT_HEADER = (
	'msgid ""\n'
	'msgstr ""\n'
	'"Content-Type: text/plain; charset=UTF-8\\n"\n'
	'"Language: en\\n"\n'
)
_PO_HEADER = (
	'msgid ""\n'
	'msgstr ""\n'
	'"Content-Type: text/plain; charset=UTF-8\\n"\n'
	'"Language: fr\\n"\n\n'
	'msgid "hello"\nmsgstr ""\n'
)


def _make_min_project(root, po_relpaths=(), pot_relpaths=()):
	"""Write minimal .po/.pot files at the given relative locations."""
	for rel in po_relpaths:
		p = root / rel
		p.parent.mkdir(parents=True, exist_ok=True)
		p.write_text(_PO_HEADER, encoding="utf-8")
	for rel in pot_relpaths:
		p = root / rel
		p.parent.mkdir(parents=True, exist_ok=True)
		p.write_text(_POT_HEADER, encoding="utf-8")


def test_detect_ignores_excluded_dirs(tmp_path):
	"""A .po buried under build/ or .venv/ must not be picked up."""
	_make_min_project(
		tmp_path,
		po_relpaths=[
			"locale/fr/LC_MESSAGES/messages.po",
			"build/vendored/locale/de/LC_MESSAGES/messages.po",
			".venv/lib/locale/es/LC_MESSAGES/messages.po",
			"node_modules/pkg/locale/it/LC_MESSAGES/messages.po",
		],
		pot_relpaths=["locale/messages.pot"],
	)
	result = detect(tmp_path)
	assert set(result["po_files"]) == {"fr"}
	assert result["pot_path"] == "locale/messages.pot"


def test_detect_pot_prefers_shallowest(tmp_path):
	"""When multiple .pot files exist, the shallowest path wins deterministically."""
	_make_min_project(
		tmp_path,
		pot_relpaths=[
			"docs/examples/nested/messages.pot",
			"locale/messages.pot",
		],
	)
	result = detect(tmp_path)
	assert result["pot_path"] == "locale/messages.pot"


def test_detect_po_root_scopes_discovery(tmp_path):
	"""--po-root restricts where we look, even across sibling dirs."""
	_make_min_project(
		tmp_path,
		po_relpaths=[
			"translations/fr.po",
			"unrelated/locale/de/LC_MESSAGES/messages.po",
		],
	)
	result = detect(tmp_path, po_root=tmp_path / "translations")
	assert set(result["po_files"]) == {"fr"}
	# Paths are still relative to project root, not po_root
	assert result["po_files"]["fr"] == "translations/fr.po"


def test_detect_project_type_ignores_venv(tmp_path):
	"""A .venv full of Python files must not flip project_type to python."""
	venv_py = tmp_path / ".venv/lib/site-packages/foo.py"
	venv_py.parent.mkdir(parents=True)
	venv_py.write_text("", encoding="utf-8")
	result = detect(tmp_path)
	assert result["project_type"] == "unknown"


def test_detect_po_root_outside_root_raises(tmp_path):
	other = tmp_path / "other"
	other.mkdir()
	proj = tmp_path / "proj"
	proj.mkdir()
	with pytest.raises(ValueError):
		detect(proj, po_root=other)


def test_detect_standard_wins_over_flat_for_same_lang(tmp_path):
	"""When both layouts hold the same lang, standard layout is preferred."""
	_make_min_project(
		tmp_path,
		po_relpaths=[
			"translations/fr.po",
			"locale/fr/LC_MESSAGES/messages.po",
		],
	)
	result = detect(tmp_path)
	assert "LC_MESSAGES" in result["po_files"]["fr"]
