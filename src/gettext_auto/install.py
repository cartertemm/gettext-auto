"""install-skill command backend."""
from __future__ import annotations

import shutil
from pathlib import Path


SKILL_DIR = "skills/gettext-auto"
COMMANDS_DIR = "commands"


def locate_source_root() -> Path:
	"""Find the dir holding skills/ and commands/.

	In a wheel install, hatchling's force-include bundles them under
	src/gettext_auto/_assets/. In an editable/dev install, they live at repo root.
	"""
	import gettext_auto
	pkg_dir = Path(gettext_auto.__file__).resolve().parent
	packaged = pkg_dir / "_assets"
	if (packaged / "skills" / "gettext-auto" / "SKILL.md").exists():
		return packaged
	# Dev layout: src/gettext_auto/ -> src/ -> repo root
	repo_root = pkg_dir.parent.parent
	if (repo_root / "skills" / "gettext-auto" / "SKILL.md").exists():
		return repo_root
	raise RuntimeError(
		"Cannot locate skill assets. Expected them bundled under "
		"gettext_auto/_assets/ or at the repo root."
	)


def install(source_root: Path, target_home: Path) -> list[str]:
	"""Copy skill files and slash command into ~/.claude/."""
	written: list[str] = []
	src_skill = source_root / SKILL_DIR
	dst_skill = target_home / ".claude" / SKILL_DIR
	if dst_skill.exists():
		shutil.rmtree(dst_skill)
	shutil.copytree(src_skill, dst_skill)
	for p in dst_skill.rglob("*"):
		if p.is_file():
			written.append(str(p.relative_to(target_home)))

	src_cmd = source_root / COMMANDS_DIR / "translate.md"
	dst_cmd = target_home / ".claude" / COMMANDS_DIR / "translate.md"
	dst_cmd.parent.mkdir(parents=True, exist_ok=True)
	shutil.copy2(src_cmd, dst_cmd)
	written.append(str(dst_cmd.relative_to(target_home)))
	return written
