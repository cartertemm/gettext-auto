import pytest

from gettext_auto import files as files_mod
from gettext_auto.config import TranslateFilesEntry


def make_entry(source, target):
	e = TranslateFilesEntry(source=source, target=target)
	errs = e.validate()
	assert errs == [], errs
	return e


def test_anchor_basic():
	assert files_mod._anchor("doc/en/**/*.md") == "doc/en"
	assert files_mod._anchor("doc/en/readme.md") == "doc/en/readme.md"
	assert files_mod._anchor("*.md") == ""
	assert files_mod._anchor("doc/**/readme.md") == "doc"


def test_compute_relpath():
	assert files_mod._compute_relpath("doc/en/guide/install.md", "doc/en/**/*.md") == "guide/install.md"
	assert files_mod._compute_relpath("doc/en/readme.md", "doc/en/**/*.md") == "readme.md"
	assert files_mod._compute_relpath("CHANGELOG.md", "CHANGELOG.md") == ""


def test_expand_substitutions():
	assert files_mod._expand("doc/{source}/x.md", "en", "fr") == "doc/en/x.md"
	assert files_mod._expand("doc/{target}/{relpath}", "en", "fr", "a/b.md") == "doc/fr/a/b.md"
	assert files_mod._expand("{source}-to-{target}", "en", "fr") == "en-to-fr"


def test_plan_simple_tree(tmp_path):
	(tmp_path / "doc/en/guide").mkdir(parents=True)
	(tmp_path / "doc/en/readme.md").write_text("# Readme", encoding="utf-8")
	(tmp_path / "doc/en/guide/install.md").write_text("# Install", encoding="utf-8")
	entries = [make_entry("doc/{source}/**/*.md", "doc/{target}/{relpath}")]
	plans = files_mod.plan(tmp_path, entries, "en", "es")
	paths = {(p["source_path"], p["target_path"]) for p in plans}
	assert paths == {
		("doc/en/readme.md", "doc/es/readme.md"),
		("doc/en/guide/install.md", "doc/es/guide/install.md"),
	}


def test_plan_single_file_no_wildcards(tmp_path):
	(tmp_path / "CHANGELOG.md").write_text("# Changelog", encoding="utf-8")
	entries = [make_entry("CHANGELOG.md", "CHANGELOG.{target}.md")]
	plans = files_mod.plan(tmp_path, entries, "en", "es")
	assert plans == [{"source_path": "CHANGELOG.md", "target_path": "CHANGELOG.es.md"}]


def test_plan_deduplicates_across_entries(tmp_path):
	"""If two entries match the same source, first one wins."""
	(tmp_path / "doc/en").mkdir(parents=True)
	(tmp_path / "doc/en/readme.md").write_text("# R", encoding="utf-8")
	entries = [
		make_entry("doc/{source}/**/*.md", "doc/{target}/{relpath}"),
		make_entry("doc/{source}/readme.md", "other/{target}.md"),
	]
	plans = files_mod.plan(tmp_path, entries, "en", "es")
	# Only one plan entry; the first config wins.
	assert len(plans) == 1
	assert plans[0]["target_path"] == "doc/es/readme.md"


def test_scan_skips_existing_target(tmp_path):
	(tmp_path / "doc/en").mkdir(parents=True)
	(tmp_path / "doc/es").mkdir()
	(tmp_path / "doc/en/readme.md").write_text("# En", encoding="utf-8")
	(tmp_path / "doc/es/readme.md").write_text("# Es (manually edited)", encoding="utf-8")
	entries = [make_entry("doc/{source}/**/*.md", "doc/{target}/{relpath}")]
	out = files_mod.scan_files(tmp_path, entries, "en", "es")
	assert out["entries"] == []


def test_scan_force_includes_existing_target(tmp_path):
	(tmp_path / "doc/en").mkdir(parents=True)
	(tmp_path / "doc/es").mkdir()
	(tmp_path / "doc/en/readme.md").write_text("# En", encoding="utf-8")
	(tmp_path / "doc/es/readme.md").write_text("# Es", encoding="utf-8")
	entries = [make_entry("doc/{source}/**/*.md", "doc/{target}/{relpath}")]
	out = files_mod.scan_files(tmp_path, entries, "en", "es", force=True)
	assert len(out["entries"]) == 1
	assert out["entries"][0]["source_path"] == "doc/en/readme.md"
	assert out["entries"][0]["content"] == "# En"


def test_scan_includes_file_content(tmp_path):
	(tmp_path / "doc/en").mkdir(parents=True)
	(tmp_path / "doc/en/readme.md").write_text("# Hello\n\nBody.", encoding="utf-8")
	entries = [make_entry("doc/{source}/**/*.md", "doc/{target}/{relpath}")]
	out = files_mod.scan_files(tmp_path, entries, "en", "es")
	assert out["entries"][0]["content"] == "# Hello\n\nBody."


def test_scan_no_source_lang_dir(tmp_path):
	"""Glob matches nothing when source dir doesn't exist. Warn, continue."""
	entries = [make_entry("doc/{source}/**/*.md", "doc/{target}/{relpath}")]
	out = files_mod.scan_files(tmp_path, entries, "en", "es")
	assert out["entries"] == []


def test_count_structure_basic():
	text = "# H1\n\n## H2\n\n[a](x) and ![img](y)\n"
	c = files_mod.count_structure(text)
	assert c == {"code_fences": 0, "headings": 2, "links": 2}


def test_count_structure_ignores_headings_in_code():
	text = "# H1\n\n```\n# not a heading\n```\n\n## H2\n"
	c = files_mod.count_structure(text)
	assert c["headings"] == 2
	# One well-formed code block = 2 fence lines.
	assert c["code_fences"] == 2


def test_count_structure_ignores_links_in_code():
	text = "[outside](x)\n\n```\n[inside](y)\n```\n"
	c = files_mod.count_structure(text)
	assert c["links"] == 1
	assert c["code_fences"] == 2


def test_verify_catches_unclosed_fence_in_translation():
	"""Regression: a translation with an odd fence count must not pass
	verification just because floor(odd/2) == floor(even/2)."""
	# Source: 2 well-formed blocks = 4 fence lines.
	source = "```\na\n```\n\n```\nb\n```\n"
	# Target: 1 closed block + 1 unclosed = 3 fence lines.
	translated = "```\na\n```\n\n```\nb\n"
	errs = files_mod.verify(source, translated)
	assert any("code_fences count mismatch" in e for e in errs)


def test_verify_passes_when_counts_match():
	source = "# Title\n\n[link](x)\n\n```\ncode\n```\n"
	translated = "# Titre\n\n[lien](x)\n\n```\ncode\n```\n"
	assert files_mod.verify(source, translated) == []


def test_verify_empty_output():
	assert files_mod.verify("# Hello", "") == ["empty output"]
	assert files_mod.verify("# Hello", "   \n\n") == ["empty output"]


def test_verify_heading_mismatch():
	source = "# A\n## B\n"
	translated = "# A\n"
	errs = files_mod.verify(source, translated)
	assert any("headings count mismatch" in e for e in errs)


def test_verify_link_mismatch():
	source = "[a](x) [b](y)"
	translated = "[a](x)"
	errs = files_mod.verify(source, translated)
	assert any("links count mismatch" in e for e in errs)


def test_verify_fence_mismatch():
	source = "```\na\n```\n\n```\nb\n```\n"
	translated = "```\na b\n```\n"
	errs = files_mod.verify(source, translated)
	assert any("code_fences count mismatch" in e for e in errs)


def test_apply_writes_translated_file(tmp_path):
	(tmp_path / "doc/en").mkdir(parents=True)
	(tmp_path / "doc/en/readme.md").write_text("# Hello\n\n[link](x)\n", encoding="utf-8")
	entries = [make_entry("doc/{source}/**/*.md", "doc/{target}/{relpath}")]
	translations = [{"id": "doc/en/readme.md", "content": "# Hola\n\n[enlace](x)\n"}]
	out = files_mod.apply_files(tmp_path, entries, "en", "es", translations)
	assert out["summary"]["written_ok"] == 1
	assert out["summary"]["verification_failed"] == 0
	assert (tmp_path / "doc/es/readme.md").read_text(encoding="utf-8") == "# Hola\n\n[enlace](x)\n"


def test_apply_skips_when_target_exists(tmp_path):
	(tmp_path / "doc/en").mkdir(parents=True)
	(tmp_path / "doc/es").mkdir()
	(tmp_path / "doc/en/readme.md").write_text("# En", encoding="utf-8")
	(tmp_path / "doc/es/readme.md").write_text("# Preserved", encoding="utf-8")
	entries = [make_entry("doc/{source}/**/*.md", "doc/{target}/{relpath}")]
	translations = [{"id": "doc/en/readme.md", "content": "# Something"}]
	out = files_mod.apply_files(tmp_path, entries, "en", "es", translations)
	assert out["summary"]["written_ok"] == 0
	assert out["summary"]["skipped"] == 1
	# Existing file is untouched.
	assert (tmp_path / "doc/es/readme.md").read_text(encoding="utf-8") == "# Preserved"


def test_apply_force_overwrites_in_place(tmp_path):
	(tmp_path / "doc/en").mkdir(parents=True)
	(tmp_path / "doc/es").mkdir()
	(tmp_path / "doc/en/readme.md").write_text("# En", encoding="utf-8")
	(tmp_path / "doc/es/readme.md").write_text("# Old", encoding="utf-8")
	entries = [make_entry("doc/{source}/**/*.md", "doc/{target}/{relpath}")]
	translations = [{"id": "doc/en/readme.md", "content": "# New"}]
	out = files_mod.apply_files(tmp_path, entries, "en", "es", translations, force=True)
	assert out["summary"]["written_ok"] == 1
	assert (tmp_path / "doc/es/readme.md").read_text(encoding="utf-8") == "# New"


def test_apply_rejects_unknown_id(tmp_path):
	entries = [make_entry("doc/{source}/**/*.md", "doc/{target}/{relpath}")]
	translations = [{"id": "does/not/exist.md", "content": "# X"}]
	out = files_mod.apply_files(tmp_path, entries, "en", "es", translations)
	assert out["summary"]["verification_failed"] == 1
	assert out["entries"][0]["status"] == "final-fail"


def test_apply_rejects_on_verify_failure(tmp_path):
	(tmp_path / "doc/en").mkdir(parents=True)
	(tmp_path / "doc/en/readme.md").write_text("# A\n## B\n", encoding="utf-8")
	entries = [make_entry("doc/{source}/**/*.md", "doc/{target}/{relpath}")]
	translations = [{"id": "doc/en/readme.md", "content": "# Only one heading"}]
	out = files_mod.apply_files(tmp_path, entries, "en", "es", translations)
	assert out["summary"]["verification_failed"] == 1
	assert not (tmp_path / "doc/es/readme.md").exists()


def test_default_nvda_entries_with_addon_root():
	info = {"addon_root": "addon", "base_manifest_path": "addon/manifest.ini", "locale_base": "addon/locale"}
	entries = files_mod.default_nvda_entries(info)
	assert len(entries) == 1
	assert entries[0].source == "addon/doc/{source}/**/*.md"
	assert entries[0].target == "addon/doc/{target}/{relpath}"


def test_default_nvda_entries_flat():
	info = {"addon_root": "", "base_manifest_path": "manifest.ini", "locale_base": "locale"}
	entries = files_mod.default_nvda_entries(info)
	assert entries[0].source == "doc/{source}/**/*.md"
	assert entries[0].target == "doc/{target}/{relpath}"


def test_effective_entries_user_wins():
	user = [make_entry("docs/{source}/**/*.md", "docs/{target}/{relpath}")]
	info = {"addon_root": "addon", "base_manifest_path": "addon/manifest.ini", "locale_base": "addon/locale"}
	result = files_mod.effective_entries(user, info)
	assert result == user


def test_effective_entries_nvda_fallback():
	info = {"addon_root": "addon", "base_manifest_path": "addon/manifest.ini", "locale_base": "addon/locale"}
	result = files_mod.effective_entries([], info)
	assert len(result) == 1
	assert result[0].source == "addon/doc/{source}/**/*.md"


def test_effective_entries_empty_when_no_config_and_no_nvda():
	assert files_mod.effective_entries([], None) == []
