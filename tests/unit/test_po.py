from pathlib import Path
import pytest
from gettext_auto.po import load_po, enumerate_pending, write_translation, entry_id


def test_load_po(fixtures_dir):
    pof = load_po(fixtures_dir / "python-partial-fr/locale/fr/LC_MESSAGES/messages.po")
    assert pof.metadata["Language"] == "fr"


def test_enumerate_pending_returns_untranslated_and_fuzzy(fixtures_dir):
    pof = load_po(fixtures_dir / "python-partial-fr/locale/fr/LC_MESSAGES/messages.po")
    pending = enumerate_pending(pof)
    msgids = {e.msgid for e in pending}
    assert msgids == {"Close", "File", "Help"}


def test_entry_id_is_stable_across_loads(fixtures_dir):
    path = fixtures_dir / "python-partial-fr/locale/fr/LC_MESSAGES/messages.po"
    a = load_po(path)
    b = load_po(path)
    assert entry_id(a[0]) == entry_id(b[0])


def test_write_translation_marks_fuzzy(tmp_path, fixtures_dir):
    src = fixtures_dir / "python-partial-fr/locale/fr/LC_MESSAGES/messages.po"
    dst = tmp_path / "fr.po"
    dst.write_bytes(src.read_bytes())
    pof = load_po(dst)
    target = next(e for e in pof if e.msgid == "File")
    write_translation(target, "Fichier")
    pof.save(str(dst))
    reloaded = load_po(dst)
    saved = next(e for e in reloaded if e.msgid == "File")
    assert saved.msgstr == "Fichier"
    assert "fuzzy" in saved.flags


def test_write_translation_does_not_touch_non_fuzzy(fixtures_dir):
    pof = load_po(fixtures_dir / "python-partial-fr/locale/fr/LC_MESSAGES/messages.po")
    already = next(e for e in pof if e.msgid == "Save")
    with pytest.raises(ValueError):
        write_translation(already, "something else")


def test_enumerate_pending_includes_empty_plural_forms(fixtures_dir):
    pof = load_po(fixtures_dir / "python-plurals/locale/pl/LC_MESSAGES/messages.po")
    pending = enumerate_pending(pof)
    assert len(pending) == 1
    assert pending[0].msgid_plural == "%d files"


def test_write_translation_allows_half_translated_plural(tmp_path, fixtures_dir):
    """A plural entry with some forms empty is pending and must be overwritable."""
    src = fixtures_dir / "python-plurals/locale/pl/LC_MESSAGES/messages.po"
    dst = tmp_path / "pl.po"
    dst.write_bytes(src.read_bytes())
    pof = load_po(dst)
    target = next(e for e in pof if e.msgid == "%d file")
    # Simulate a half-translated plural: form 0 set, form 1 empty.
    target.msgstr_plural = {0: "Un", 1: "", 2: ""}
    # Sanity: enumerate_pending still treats it as pending.
    assert target in enumerate_pending(pof)
    # write_translation must accept it rather than refusing.
    write_translation(target, "", msgstr_plural=["Un fichier", "%d fichiers", "%d fichierow"])
    assert "fuzzy" in target.flags
    assert target.msgstr_plural[0] == "Un fichier"
    assert target.msgstr_plural[1] == "%d fichiers"
