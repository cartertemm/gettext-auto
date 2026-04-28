# gettext-auto

Welcome to gettext-auto!
This is a [Claude Code](https://www.anthropic.com/claude-code) skill that translates gettext-based projects into different languages using AI.

Most software is written in English, yet [around 75% of people browsing the web don't use English as their native language](https://parkmagazineny.com/75-of-internet-users-are-non-english-speakers-why-startups-ignoring-multilingual-growth-are-falling-behind/). If you've ever tried to localize a codebase, you know it's a slog. This project was built on three beliefs:

- A buggy translation is better than no translation at all.
- Language models can move content between languages with reasonable accuracy.
- Humans will always be better at making sure text reads well in their own language. AI can fill in the gaps in the meantime, or give them a point to start.

With gettext-auto you focus on shipping, the model handles the boring first pass, then a native speaker comes in later to fix the parts it got wrong.

## Features

- Translates `.po` files one language at a time using whichever model Claude Code is currently running.
- Picks up your `.pot` and `.po` files automatically, regardless of how your project is laid out. Whether flat, nested, the standard `locale/<lang>/LC_MESSAGES/` layout, or something different, the skill will figure it out.
- Respects fuzzy flags.
- Never overwrites an entry a human has already reviewed and cleared.
- Writes every translation as fuzzy so nothing the model produced ships until someone signs off on it.
- Verifies placeholders and plural counts before writing. If something is off, the entry gets an `AUTOTRANS-ERROR:` comment so `msgfmt` catches it.
- First class support for NVDA screen reader add-ons translates `summary` and `description` from manifest.ini in the same pass.
- Translates markdown docs (readme, user guide, changelog, whatever you point it at) one whole file at a time. Verifies heading, code-fence, and link counts match the source before writing.

## Installation

You'll need [uv](https://docs.astral.sh/uv/getting-started/installation/) and [Claude Code](https://www.anthropic.com/claude-code).

From within Claude Code, paste something like:

```
Install gettext-auto from https://github.com/cartertemm/gettext-auto by running `uv tool install git+https://github.com/cartertemm/gettext-auto`, and then `gettext-auto install-skill`.
```

Or do it yourself:

```bash
uv tool install git+https://github.com/cartertemm/gettext-auto
```

If you plan to translate NVDA add-ons, you'll need configobj. Install the extra instead so the manifest commands work:

```bash
uv tool install "gettext-auto[nvda] @ git+https://github.com/cartertemm/gettext-auto"
```

finally, run:

```
gettext-auto install-skill
```

`install-skill` copies the skill and `/translate` slash command into `~/.claude/`. Run `gettext-auto uninstall-skill` to remove them.

## Quickstart

Open a project that uses gettext. From inside Claude Code:

```
/translate es
```

The skill will:

1. Detect your project layout and find the .pot and .po files.
2. Create an `es.po` from the .pot if you don't have one yet.
3. Pull pending entries in batches, translate them, verify them, and write them back as fuzzy.
4. Print a summary of what got written, what failed verification, and anything msgfmt flagged.

Language codes are BCP-47 / ISO style: `fr`, `pt_BR`, `zh_Hans`, etc.

If the skill finds .po files somewhere unexpected like a vendored dependency or build output folder, it'll stop and ask you to confirm the canonical location before touching anything. You can pass `--po-root <dir>` to scope discovery to a specific subdirectory.

## Options

The skill is a thin wrapper around the `gettext-auto` CLI. You can run any of these directly:

- `gettext-auto detect` prints what the skill is given for the context of your project including project type, layout, existing .po files, source language.
- `gettext-auto extract` runs pybabel to pull msgids from source into the .pot.
- `gettext-auto init-po <lang>` creates a new .po catalog from the .pot.
- `gettext-auto update-po` merges new and removed msgids from the .pot into every existing .po.
- `gettext-auto scan <lang>` lists pending entries for a language as JSON.
- `gettext-auto apply <lang>` takes translated JSON on stdin and writes it back to the .po, verifying placeholders and plural counts as it goes.
- `gettext-auto compile` compiles every .po to a .mo.
- `gettext-auto files scan <lang>` lists markdown / doc files that have a source but no translated target yet, configured via `[[translate_files]]` (see Configuration). Pass `--force` to include files whose target already exists.
- `gettext-auto files apply <lang>` takes translated JSON on stdin and writes each entry to its target. Existing targets are left alone unless `--force` is passed.

All of the discovery commands accept `--po-root` and `--cwd`.

If your project is an NVDA add-on, you want to use `gettext-auto nvda scan <lang>` and `gettext-auto nvda apply <lang>` for the manifest. Claude Code will handle this for you if it needs it. NVDA add-ons also get a built-in default for `translate_files` that mirrors `addon/doc/<source>/**/*.md` into `addon/doc/<target>/...` without any config.

## Configuration

If the defaults don't suit you, drop a `.gettext-auto.toml` somewhere gettext-auto can find it. It checks three places in this order and uses whichever one turns up first:

1. `<project>/.gettext-auto.toml`
2. `<project>/.claude/.gettext-auto.toml`
3. `~/.claude/.gettext-auto.toml`

Running `gettext-auto init-config` writes a commented template into the current directory so you can see what's available. Add `--global` to write it under `~/.claude/` instead.

Every key is optional:

```toml
author_name = "Jane Smith"       # Name on the Last-Translator header. "{git}" reads `git config user.name`.
author_email = "jane@acme.com"   # Same idea. "{git}" reads `git config user.email`.
mark_fuzzy = true                # Mark every AI translation fuzzy so msgfmt won't compile until a human signs off. Keep this on.
context = "Technical audience, US English source, keep NVDA untranslated."
language_team = "French <fr-team@acme.com>"
report_bugs_to = "bugs@acme.com"
```

Out of the box your git identity goes into the Last-Translator header, which is usually what you want. If you'd rather not have your name attached to machine output, point `author_name` and `author_email` at a project email or bot account before running.

### Translating doc files

Markdown and other prose files are driven by one or more `[[translate_files]]` entries. Each maps a source glob to a target path template:

```toml
[[translate_files]]
source = "doc/{source}/**/*.md"
target = "doc/{target}/{relpath}"

[[translate_files]]
source = "CHANGELOG.md"
target = "CHANGELOG.{target}.md"
```

- `{source}` and `{target}` get substituted with language codes.
- `{relpath}` is the wildcard portion of the match. For a glob `doc/{source}/**/*.md` matched against `doc/en/guide/install.md`, `{relpath}` is `guide/install.md`, and the target resolves to `doc/es/guide/install.md`.
- `{target}` in the target template is required. `{relpath}` only makes sense when the source has wildcards.
- Multiple entries are allowed. First entry to claim a source file wins.
- Existing target files are left alone. Delete them or run `gettext-auto files scan <lang> --force` to regenerate.

NVDA add-ons get a default entry that covers `addon/doc/<lang>/**/*.md` (or `doc/<lang>/**/*.md` for flat layouts) when no user `[[translate_files]]` is configured.

## Roadmap

Things that I want to have happen:

- [ ] Expand beyond claude code to include a Codex skill
- [ ] Standalone support using i.e. "LLM" for people that do not have coding agent subscriptions
- [ ] `--retry` on `apply` for entries that failed verification the first time
- [ ] Support for gettext frontends beyond pybabel (raw xgettext, `scons pot`, etc.)
- [ ] A proper progress indicator for long runs

Pull requests welcome for any of these, or for things I haven't thought of.

## Contributing

I wrote this to try and cut down on the pervasive localization problem, and so that people no longer have to spend entire afternoons in a .po editor when they just want to ship something.

It is not polished, that will come with time. There are potentially layouts and project shapes I haven't seen that it may not handle well.

If it breaks on your project, open an issue and tell me what you were trying to do and what happened. If the fix is obvious and you know how to fix it, please submit a PR!
