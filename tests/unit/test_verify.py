from gettext_auto.verify import verify_entry


def test_printf_simple_ok():
	assert verify_entry("Hello, %s!", "Bonjour, %s !").errors == []


def test_printf_missing_placeholder():
	errs = verify_entry("Hello, %s!", "Bonjour !").errors
	assert any("%s" in e for e in errs)


def test_named_printf_ok_reordered():
	src = "%(name)s logged in at %(time)s"
	dst = "%(time)s : %(name)s s'est connecté"
	assert verify_entry(src, dst).errors == []


def test_named_printf_missing():
	src = "%(name)s logged in"
	dst = "connecté"
	assert verify_entry(src, dst).errors != []


def test_brace_ok():
	assert verify_entry("Items: {0}", "Articles : {0}").errors == []


def test_brace_conversion_preserved():
	assert verify_entry("Open {name!r}", "Ouvrir {name!r}").errors == []


def test_double_percent_literal_preserved():
	assert verify_entry("100%% done", "Terminé à 100%%").errors == []


def test_double_percent_stripped_fails():
	assert verify_entry("100%% done", "Terminé à 100% done").errors != []


def test_html_tag_missing():
	errs = verify_entry("<b>Warning</b>", "Attention").errors
	assert any("<b>" in e or "tag" in e.lower() for e in errs)


def test_html_tag_preserved():
	assert verify_entry("<b>Warning</b>", "<b>Attention</b>").errors == []


def test_plural_count_ok():
	result = verify_entry(
		msgid="%d file",
		msgstr=None,
		msgid_plural="%d files",
		msgstr_plural=["%d plik", "%d pliki", "%d plików"],
		nplurals=3,
	)
	assert result.errors == []


def test_plural_count_wrong():
	result = verify_entry(
		msgid="%d file",
		msgstr=None,
		msgid_plural="%d files",
		msgstr_plural=["%d plik", "%d pliki"],
		nplurals=3,
	)
	assert any("3" in e or "plural" in e.lower() for e in result.errors)
