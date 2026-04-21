"""Layout scaffolder. No application-code edits in v2."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


BABEL_CFG = """\
[python: **.py]
"""

LOCALE_README = """\
# locale/

This directory holds gettext catalogs managed by gettext-auto.

Workflow:
  gettext-auto extract           # source .py -> locale/messages.pot
  gettext-auto init-po <lang>    # new language .po from the .pot
  gettext-auto update-po         # merge new/removed msgids into every .po
  gettext-auto compile           # every .po -> .mo binary

Translate interactively with `/translate <lang>` inside Claude Code.
"""


@dataclass
class ScaffoldPlan:
	files: dict[str, str]  # relpath -> content

	def preview(self) -> str:
		lines = ["Planned changes:"]
		for rel in sorted(self.files):
			lines.append(f"  + {rel}")
		return "\n".join(lines)

	def write(self, root: Path) -> None:
		for rel, content in self.files.items():
			target = root / rel
			target.parent.mkdir(parents=True, exist_ok=True)
			target.write_text(content, encoding="utf-8")


def plan_layout(root: Path, domain: str = "messages", source_lang: str = "en") -> ScaffoldPlan:
	files = {
		"babel.cfg": BABEL_CFG,
		"locale/README.md": LOCALE_README,
		f"locale/{domain}.pot": _empty_pot(domain, source_lang),
	}
	return ScaffoldPlan(files=files)


def _empty_pot(domain: str, source_lang: str) -> str:
	return (
		'# Translations template.\n'
		'#\n'
		'msgid ""\n'
		'msgstr ""\n'
		f'"Project-Id-Version: {domain} 0.1\\n"\n'
		'"Content-Type: text/plain; charset=UTF-8\\n"\n'
		'"Content-Transfer-Encoding: 8bit\\n"\n'
		f'"Language: {source_lang}\\n"\n'
	)
