from pathlib import Path
from gettext_auto.install import install, locate_source_root


def test_install_copies_skill_and_command(tmp_path):
	home = tmp_path / "home"
	home.mkdir()
	pkg = tmp_path / "pkg"
	(pkg / "skills/gettext-auto").mkdir(parents=True)
	(pkg / "skills/gettext-auto/SKILL.md").write_text("skill body", encoding="utf-8")
	(pkg / "commands").mkdir()
	(pkg / "commands/translate.md").write_text("slash body", encoding="utf-8")

	install(source_root=pkg, target_home=home)

	assert (home / ".claude/skills/gettext-auto/SKILL.md").read_text(encoding="utf-8") == "skill body"
	assert (home / ".claude/commands/translate.md").read_text(encoding="utf-8") == "slash body"


def test_locate_source_root_prefers_packaged_assets(tmp_path, monkeypatch):
	"""When gettext_auto/_assets/ exists (post-install), use it."""
	import gettext_auto
	pkg_dir = Path(gettext_auto.__file__).resolve().parent
	assets = pkg_dir / "_assets"
	# If assets are bundled (wheel install), locate_source_root must point at them.
	if (assets / "skills" / "gettext-auto" / "SKILL.md").exists():
		assert locate_source_root() == assets
	else:
		# Dev layout: repo root two levels up from src/gettext_auto/
		repo_root = pkg_dir.parent.parent
		assert locate_source_root() == repo_root
