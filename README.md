# gettext-auto

Welcome to gettext-auto!
This is a [Claude Code](https://www.anthropic.com/claude-code) skill that translates gettext-based projects into other languages using AI.

Most software is written in English, yet [around 75% of people browsing the web don't use English as their native language](https://parkmagazineny.com/75-of-internet-users-are-non-english-speakers-why-startups-ignoring-multilingual-growth-are-falling-behind/). If you've ever tried to localize a codebase, you know it's a slog. This project was built on three beliefs:

- A buggy translation is better than no translation at all.
- Language models can move content between languages with reasonable accuracy.
- Humans will always be better at making sure text reads well in their own language. AI can fill in the gaps in the meantime, or give them a point to start.

You focus on shipping. The model handles the boring first pass. A native speaker comes in later to clean up the parts it got wrong.

## Install

You'll need [Claude Code](https://www.anthropic.com/claude-code) and [uv](https://docs.astral.sh/uv/getting-started/installation/).

In a terminal:

```bash
uv tool install git+https://github.com/cartertemm/gettext-auto
gettext-auto install-skill
```

That installs the tool and copies the `/translate` slash command into `~/.claude/`. To remove everything later, run `gettext-auto uninstall-skill`.

If you'd rather not touch a terminal, paste this into Claude Code and let it do the install for you:

> Install gettext-auto from https://github.com/cartertemm/gettext-auto by running `uv tool install git+https://github.com/cartertemm/gettext-auto`, then `gettext-auto install-skill`.

Translating an NVDA add-on? See the [NVDA add-ons](#nvda-add-ons) section for one extra install step.

## Quickstart

Open a project that already uses gettext (it has a `.pot` file or some `.po` files). From inside Claude Code:

```
/translate es
```

Replace `es` with whatever language you want. Use BCP-47 / ISO codes, so `fr`, `pt_BR`, `zh_Hans`, that kind of thing.

The skill will:

1. Find your `.pot` and `.po` files, wherever they live in the repo.
2. Create `es.po` if you don't have one yet.
3. Translate each pending entry, check the result for obvious problems, and write it back.
4. If you've configured doc-file translation (see [Configuration](#configuration)), translate any matching markdown files in the same pass.
5. Print a summary of what got written.

A finished run looks something like:

```
Translated 47 entries into es.po (all marked fuzzy for review).
Verification failed: 0
Doc files written: 1 (doc/es/readme.md)

Review the fuzzy entries in your favorite .po editor and ship when you're happy.
```

If your project doesn't have a `.pot` yet, the skill will stop and tell you to set one up first. Wrapping source strings in `_()` and pulling them into a `.pot` is the standard gettext setup; once that's done, re-run `/translate es`.

## What "fuzzy" means (and how to skip it)

Every translation gets written with the gettext **fuzzy flag**. Fuzzy means "machine-translated, needs human review." It's the safety net: `msgfmt` won't compile a fuzzy entry into the production `.mo` catalog, so nothing the model produced ships until somebody clears the flag.

To review fuzzy entries:

- Open the `.po` in [poedit](https://poedit.net/) and step through each one. It surfaces fuzzy entries first and gives you a button to clear them.
- Or open the `.po` in any text editor and look for `#, fuzzy` lines above each entry; delete those lines to clear the flag.

When you're satisfied, compile to `.mo` and ship.

### YOLO mode

If you don't speak the target language anyway, reviewing every entry isn't going to help anyone. Two ways to skip the review step:

**Option 1: Tell the skill not to mark fuzzy in the first place.**

In `.gettext-auto.toml`:

```toml
mark_fuzzy = false
```

Now every AI translation lands clean and `msgfmt` will happily compile it. Run `/translate es` and you're done.

**Option 2: Clear all fuzzy flags after the run.**

Leave the config alone, and after `/translate es` finishes, run:

```bash
msgattrib --clear-fuzzy --output-file=es.po es.po
```

Same outcome.

Either way, expect a native speaker to file issues against your translations once real users see them. That's fine. A buggy translation is better than no translation.

## Will it overwrite my work?

No. The skill is built to be safe to re-run.

- **Cleared (non-fuzzy) entries** in your `.po` files are never touched. Once a human has reviewed and signed off on a translation, the skill leaves it alone forever.
- **Existing translated markdown files** are left alone too. If `doc/es/readme.md` already exists, the skill won't replace it. Delete the file if you want a fresh translation.
- **Verification failures** never write. If the model returns malformed output (mismatched placeholders, missing code fences in a markdown file), the entry gets reported and the file is not changed.

In short, you can run `/translate es` as many times as you want; it will only ever fill in gaps.

## Privacy

Translation runs through whichever model Claude Code is using, so every msgid in your `.po` files and every byte of every markdown file matched by your config ends up in a prompt. If your sources contain API keys, internal URLs, NDA material, or anything else you wouldn't paste into a chat window, look before you run. The tool doesn't filter for you.

## Configuration

For most projects you don't need to configure anything. The defaults are sensible.

If you want to customize, drop a `.gettext-auto.toml` somewhere the tool can find it. It checks these places, first match wins:

1. `<project>/.gettext-auto.toml`
2. `<project>/.claude/.gettext-auto.toml`
3. `~/.claude/.gettext-auto.toml`

`gettext-auto init-config` writes a commented template into the current directory so you can see every option in one place. Add `--global` to put the template in `~/.claude/` instead.

Every key below is optional.

### Translator identity

```toml
author_name = "Jane Smith"
author_email = "jane@acme.com"
```

These go into the `Last-Translator` header of your `.po` files. The default for both is `"{git}"`, which reads `git config user.name` and `user.email` at translation time. Set explicit values if you'd rather a project email or a bot account get the credit instead of you.

### Review safety net

```toml
mark_fuzzy = true
```

`true` (the default) marks every AI translation as fuzzy so `msgfmt` won't compile until a human clears them. Set to `false` for [YOLO mode](#yolo-mode).

### Project context

```toml
context = "NVDA is a Windows screen reader; audience is blind developers."
```

A short description of your project, passed to the model as extra context. Helps when the same word means different things in different domains.

### Standard .po headers

```toml
language_team = "French <fr-team@acme.com>"
report_bugs_to = "bugs@acme.com"
```

Optional headers written into your `.po` files. Skip them unless you specifically want them.

### Translating doc files

To translate markdown (or other prose files) alongside your `.po` files, declare one or more `[[translate_files]]` entries. Each maps a source glob to a target path template:

```toml
[[translate_files]]
source = "doc/{source}/**/*.md"
target = "doc/{target}/{relpath}"
```

What that says: translate every `.md` file under `doc/<source-language>/` into a matching path under `doc/<target-language>/`. So `doc/en/guide/install.md` becomes `doc/es/guide/install.md` for a Spanish run.

- `{source}` and `{target}` are replaced with language codes.
- `{relpath}` is the wildcard portion of each match.
- You can have multiple entries; the first to claim a source file wins.
- Existing target files are never overwritten. Delete them to regenerate.

NVDA add-ons get a sensible default for this without any config (see [NVDA add-ons](#nvda-add-ons)).

## NVDA add-ons

[NVDA](https://www.nvaccess.org/) is a free, open-source screen reader for Windows. Its add-on ecosystem has its own conventions, and gettext-auto handles them out of the box.

If your project is an NVDA add-on (we detect this by looking for `addon/manifest.ini`, or `manifest.ini` next to a `locale/` directory), the skill will:

- Translate the `summary` and `description` fields from the add-on's `manifest.ini` for each language, in the same pass.
- Translate any markdown docs under `addon/doc/<lang>/` (or `doc/<lang>/` for flat layouts) into the target language. No `[[translate_files]]` config needed.

You'll need the optional `configobj` dependency for the manifest part to work. Install with the `[nvda]` extra:

```bash
uv tool install "gettext-auto[nvda] @ git+https://github.com/cartertemm/gettext-auto"
```

If you already installed without the extra, run that command again; uv will replace the existing install.

## How it works under the hood

`/translate` is a small skill that orchestrates a CLI named `gettext-auto`. The CLI does all the deterministic work: finding your `.pot` and `.po` files, matching globs, verifying that placeholders and plural counts line up, never overwriting cleared entries. The model does the actual translation: the CLI hands it a batch of pending entries as JSON, the model returns translated JSON, the CLI verifies and writes.

You don't normally need to touch the CLI. It exists if you want to script around the tool or debug something the skill is doing. Output is JSON, intended for machine consumption rather than humans. Run `gettext-auto --help` for the list of subcommands.

The split between CLI and model is deliberate. Anything that has a right answer (where the .po lives, whether placeholders survived, whether you've already reviewed an entry) stays out of the model's hands.

## Roadmap

Things I'd like to ship next:

- A Codex / non-Claude skill so this isn't tied to one platform.
- Standalone support for people without coding-agent subscriptions, probably via [llm](https://llm.datasette.io/).
- Retry on verification failure rather than reporting and moving on.
- Support for non-pybabel gettext frontends (raw `xgettext`, `scons pot`, etc.).
- A progress indicator for long runs.

Pull requests welcome for any of these or for things I haven't thought of.

## Contributing

Clone, install with the dev extras, run the tests:

```bash
git clone https://github.com/cartertemm/gettext-auto
cd gettext-auto
uv sync --extra dev --extra nvda
uv run pytest
```

If you're adding behavior, add a test. If you're fixing a bug, add a test that fails before the fix and passes after. Tests live in `tests/unit/` and `tests/integration/`; sample projects to test against are in `tests/fixtures/`.

If something breaks on your project, open an issue and tell me what you were trying to do and what happened. If the fix is obvious and you know how to fix it, send a PR.

It's not polished. There are layouts and project shapes I haven't seen that may not handle well. Help me find them.
