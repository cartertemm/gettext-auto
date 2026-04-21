# gettext-auto

AI-assisted gettext translation skill for Claude Code. Run `/translate <lang>` inside a project with gettext catalogs and the skill translates pending entries, writing them back as `fuzzy` for your review.

## Install

```bash
git clone https://github.com/cartertemm/gettext-auto
uv tool install .
gettext-auto install-skill
```

`install-skill` copies the skill and `/translate` slash command into `~/.claude/`.

## Quickstart

In a Claude Code session, inside a project with `.po` files:

```
/translate fr
```

The skill detects the project and the location of the translations, then scans for untranslated/fuzzy entries, translates them, and writes the results back as fuzzy. Review in your editor, then commit.
