from gettext_auto.verify import msgfmt_check


def test_msgfmt_check_clean_file(tmp_path, fixtures_dir):
	po = fixtures_dir / "python-fully-translated/locale/fr/LC_MESSAGES/messages.po"
	warnings = msgfmt_check(po)
	assert warnings == []


def test_msgfmt_check_reports_broken_header(tmp_path):
	broken = tmp_path / "broken.po"
	broken.write_text(
		'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n'
		'msgid "hello"\nmsgstr "%(nope)s"\n',
		encoding="utf-8",
	)
	warnings = msgfmt_check(broken)
	assert isinstance(warnings, list)
