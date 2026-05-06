import json
import os
import re
import sys
from pathlib import Path

import click
from babel.messages.frontend import CommandLineInterface as BabelCLI

from gettext_auto import config as config_mod
from gettext_auto import project
from gettext_auto import po as po_mod
from gettext_auto import verify as verify_mod
from gettext_auto import install as install_mod
from gettext_auto import nvda as nvda_mod
from gettext_auto import files as files_mod


def _resolve_home() -> Path:
	return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home()))


def _parse_nplurals(plural_rule: str) -> int:
	m = re.search(r"nplurals\s*=\s*(\d+)", plural_rule)
	return int(m.group(1)) if m else 2


def _resolve_po_root(cwd: str, po_root: str | None) -> Path | None:
	"""Resolve --po-root against --cwd. Absolute paths are used as-is."""
	if po_root is None:
		return None
	p = Path(po_root)
	if not p.is_absolute():
		p = Path(cwd) / p
	if not p.is_dir():
		raise click.ClickException(f"--po-root {str(p)!r} is not a directory")
	return p


@click.group()
@click.version_option()
def main():
	"""AI-assisted gettext translation."""


@main.command()
@click.option("--cwd", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--po-root", default=None,
			  help="Restrict .po/.pot discovery to this subdirectory of the project.")
def detect(cwd, po_root):
	"""Detect project state. Emits JSON to stdout."""
	po_root_path = _resolve_po_root(cwd, po_root)
	result = project.detect(Path(cwd), po_root=po_root_path)
	click.echo(json.dumps(result, indent=2))


@main.command()
@click.argument("lang")
@click.option("--cwd", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--batch", type=int, default=50)
@click.option("--examples", "examples_n", type=int, default=40)
@click.option("--po-root", default=None,
			  help="Restrict .po/.pot discovery to this subdirectory of the project.")
def scan(lang, cwd, batch, examples_n, po_root):
	"""Enumerate pending entries for <lang>. Emits JSON to stdout."""
	po_root_path = _resolve_po_root(cwd, po_root)
	det = project.detect(Path(cwd), po_root=po_root_path)
	po_rel = det["po_files"].get(lang)
	if not po_rel:
		raise click.ClickException(f"No .po file found for '{lang}'")
	po_path = Path(cwd) / po_rel
	pof = po_mod.load_po(po_path)
	pending = po_mod.enumerate_pending(pof)[:batch]
	entries = [po_mod.serialize_entry(e) for e in pending]
	examples = po_mod.clean_translations(pof, examples_n)
	cfg = config_mod.load_config(Path(cwd))
	out = {
		"project": {
			"source_lang": det["source_lang"] or "en",
			"target_lang": lang,
			"plural_rule": po_mod.plural_rule(pof),
			"context": cfg.context,
		},
		"entries": entries,
		"examples": examples,
	}
	click.echo(json.dumps(out, indent=2))


@main.command()
@click.argument("lang")
@click.option("--cwd", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--input", "input_path", default="-")
@click.option("--output", "output_path", default="-")
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--po-root", default=None,
			  help="Restrict .po/.pot discovery to this subdirectory of the project.")
def apply(lang, cwd, input_path, output_path, dry_run, po_root):
	"""Verify translations and write results back to <lang>.po."""
	raw = sys.stdin.buffer.read().decode("utf-8") if input_path == "-" else Path(input_path).read_text(encoding="utf-8")
	payload = json.loads(raw)
	po_root_path = _resolve_po_root(cwd, po_root)
	det = project.detect(Path(cwd), po_root=po_root_path)
	po_rel = det["po_files"].get(lang)
	if not po_rel:
		raise click.ClickException(f"No .po file for '{lang}'")
	po_path = Path(cwd) / po_rel
	pof = po_mod.load_po(po_path)
	nplurals = _parse_nplurals(po_mod.plural_rule(pof))
	by_id = {po_mod.entry_id(e): e for e in pof}
	cfg = config_mod.load_config(Path(cwd))
	entries_out: list[dict] = []
	summary = {"written_ok": 0, "verification_failed": 0, "msgfmt_warnings": 0}
	any_written = False
	for tr in payload["translations"]:
		eid = tr["id"]
		entry = by_id.get(eid)
		if entry is None:
			entries_out.append({"id": eid, "status": "final-fail",
								"errors": ["id not found"], "written": False, "fuzzy": False})
			summary["verification_failed"] += 1
			continue
		msgstr = tr.get("msgstr", "") or ""
		msgstr_plural = tr.get("msgstr_plural")
		result = verify_mod.verify_entry(
			entry.msgid, msgstr,
			msgid_plural=entry.msgid_plural or None,
			msgstr_plural=msgstr_plural,
			nplurals=nplurals if entry.msgid_plural else None,
		)
		try:
			if result.errors:
				existing_lines = [
					line for line in (entry.comment or "").splitlines()
					if not line.startswith("AUTOTRANS-ERROR:")
				]
				error_comment = "AUTOTRANS-ERROR: " + "; ".join(result.errors)
				entry.comment = "\n".join(existing_lines + [error_comment]).strip()
			po_mod.write_translation(
				entry, msgstr, msgstr_plural=msgstr_plural, mark_fuzzy=cfg.mark_fuzzy,
			)
			any_written = True
			is_fuzzy = "fuzzy" in entry.flags
			if result.errors:
				summary["verification_failed"] += 1
				entries_out.append({
					"id": eid, "status": "final-fail", "errors": result.errors,
					"written": True, "fuzzy": is_fuzzy,
				})
			else:
				summary["written_ok"] += 1
				entries_out.append({
					"id": eid, "status": "ok", "errors": [],
					"written": True, "fuzzy": is_fuzzy,
				})
		except ValueError as e:
			entries_out.append({"id": eid, "status": "final-fail", "errors": [str(e)],
								"written": False, "fuzzy": False})
			summary["verification_failed"] += 1

	if any_written:
		name, email = config_mod.resolve_author(cfg, Path(cwd))
		po_mod.update_po_headers(
			pof,
			last_translator=config_mod.format_last_translator(name, email),
			language_team=cfg.language_team,
			revision_date=True,
		)

	if not dry_run:
		tmp = po_path.with_suffix(po_path.suffix + ".tmp")
		pof.save(str(tmp))
		os.replace(tmp, po_path)
		warnings = verify_mod.msgfmt_check(po_path)
		summary["msgfmt_warnings"] = len(warnings)

	out = {"summary": summary, "entries": entries_out}
	text = json.dumps(out, indent=2)
	if output_path == "-":
		click.echo(text)
	else:
		Path(output_path).write_text(text, encoding="utf-8")


def _run_pybabel(argv: list[str]) -> tuple[int, str]:
	"""Run pybabel. Returns (code, error_message). 0 on success."""
	try:
		code = BabelCLI().run(["pybabel", *argv])
		return (int(code or 0), "")
	except SystemExit as e:
		return (int(e.code) if e.code else 1, f"pybabel exited with code {e.code}")
	except FileNotFoundError as e:
		return (1, f"pybabel: {e}")
	except Exception as e:
		return (1, f"pybabel: {e}")


def _pot_output_path(det: dict, domain: str) -> str:
	"""Where extract should write the .pot. Preserve existing location if any."""
	if det["pot_path"]:
		return det["pot_path"]
	po_base = det["layout"]["po_base"]
	return f"{po_base}/{domain}.pot"


def _po_output_path(layout: dict, lang: str, domain: str, nvda_info: dict | None = None) -> str:
	"""Where init-po should write a new <lang>.po, mirroring the layout."""
	if nvda_info is not None:
		return f"{nvda_info['locale_base']}/{lang}/LC_MESSAGES/nvda.po"
	po_base = layout["po_base"]
	if layout["style"] == "standard":
		return f"{po_base}/{lang}/LC_MESSAGES/{domain}.po"
	return f"{po_base}/{lang}.po"


@main.command()
@click.option("--cwd", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--domain", default=None)
@click.option("--po-root", default=None,
			  help="Restrict .po/.pot discovery to this subdirectory of the project.")
def extract(cwd, domain, po_root):
	"""Extract msgids from source into the project's .pot file."""
	root = Path(cwd)
	po_root_path = _resolve_po_root(cwd, po_root)
	det = project.detect(root, po_root=po_root_path)
	dom = domain or det["layout"]["domain"]
	pot_rel = _pot_output_path(det, dom)
	pot_abs = root / pot_rel
	pot_abs.parent.mkdir(parents=True, exist_ok=True)
	os.chdir(cwd)
	code, msg = _run_pybabel([
		"extract", "-F", "babel.cfg", "-o", pot_rel, ".",
	])
	if code:
		raise click.ClickException(f"extract failed: {msg}" if msg else f"extract failed for {pot_rel}")
	cfg = config_mod.load_config(root)
	if cfg.report_bugs_to and pot_abs.is_file():
		pof = po_mod.load_po(pot_abs)
		po_mod.update_po_headers(pof, report_bugs_to=cfg.report_bugs_to)
		pof.save(str(pot_abs))


@main.command("init-po")
@click.argument("lang")
@click.option("--cwd", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--domain", default=None)
@click.option("--po-root", default=None,
			  help="Restrict .po/.pot discovery to this subdirectory of the project.")
def init_po(lang, cwd, domain, po_root):
	"""Create a new <lang>.po from the .pot."""
	root = Path(cwd)
	po_root_path = _resolve_po_root(cwd, po_root)
	det = project.detect(root, po_root=po_root_path)
	dom = domain or det["layout"]["domain"]
	if not det["pot_path"]:
		raise click.ClickException("init-po failed: no .pot file found; run extract first")
	pot_rel = det["pot_path"]
	po_rel = _po_output_path(det["layout"], lang, dom, nvda_info=det["nvda"])
	po_abs = root / po_rel
	po_abs.parent.mkdir(parents=True, exist_ok=True)
	os.chdir(cwd)
	code, msg = _run_pybabel([
		"init", "--input-file", pot_rel, "--output-file", po_rel,
		"--locale", lang, "--domain", dom,
	])
	if code:
		raise click.ClickException(f"init-po failed: {msg}" if msg else f"init-po failed for {po_rel}")
	cfg = config_mod.load_config(root)
	name, email = config_mod.resolve_author(cfg, root)
	last_translator = config_mod.format_last_translator(name, email)
	if (last_translator or cfg.language_team or cfg.report_bugs_to) and po_abs.is_file():
		pof = po_mod.load_po(po_abs)
		po_mod.update_po_headers(
			pof,
			last_translator=last_translator,
			language_team=cfg.language_team,
			report_bugs_to=cfg.report_bugs_to,
		)
		pof.save(str(po_abs))


@main.command("update-po")
@click.option("--cwd", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--domain", default=None)
@click.option("--po-root", default=None,
			  help="Restrict .po/.pot discovery to this subdirectory of the project.")
def update_po(cwd, domain, po_root):
	"""Merge new/removed msgids from .pot into every existing .po."""
	root = Path(cwd)
	po_root_path = _resolve_po_root(cwd, po_root)
	det = project.detect(root, po_root=po_root_path)
	dom = domain or det["layout"]["domain"]
	if not det["pot_path"]:
		raise click.ClickException("update-po failed: no .pot file found; run extract first")
	if not det["po_files"]:
		click.echo("update-po: no .po files to update")
		return
	pot_rel = det["pot_path"]
	failures: list[str] = []
	messages: list[str] = []
	os.chdir(cwd)
	for lang, po_rel in det["po_files"].items():
		code, msg = _run_pybabel([
			"update", "--input-file", pot_rel, "--output-file", po_rel,
			"--locale", lang, "--domain", dom,
		])
		if code:
			failures.append(po_rel)
			if msg:
				messages.append(msg)
	if failures:
		detail = "; ".join(messages) if messages else ", ".join(failures)
		raise click.ClickException(f"update-po failed: {detail}")


@main.command("compile")
@click.option("--cwd", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--domain", default=None)
@click.option("--po-root", default=None,
			  help="Restrict .po/.pot discovery to this subdirectory of the project.")
def compile_cmd(cwd, domain, po_root):
	"""Compile every .po to .mo."""
	root = Path(cwd)
	po_root_path = _resolve_po_root(cwd, po_root)
	det = project.detect(root, po_root=po_root_path)
	if not det["po_files"]:
		click.echo("compile: no .po files to compile")
		return
	failures: list[str] = []
	messages: list[str] = []
	os.chdir(cwd)
	for lang, po_rel in det["po_files"].items():
		mo_rel = str(Path(po_rel).with_suffix(".mo")).replace("\\", "/")
		code, msg = _run_pybabel([
			"compile", "--input-file", po_rel, "--output-file", mo_rel,
			"--locale", lang,
		])
		if code:
			failures.append(po_rel)
			if msg:
				messages.append(msg)
	if failures:
		detail = "; ".join(messages) if messages else ", ".join(failures)
		raise click.ClickException(f"compile failed: {detail}")


@main.command("init-config")
@click.option("--cwd", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--global", "global_", is_flag=True, default=False,
			  help=f"Write to ~/.claude/{config_mod.CONFIG_FILENAME} instead of <cwd>.")
@click.option("--force", is_flag=True, default=False,
			  help="Overwrite an existing config file.")
def init_config(cwd, global_, force):
	"""Drop a commented .gettext-auto.toml here so the options are easy to find."""
	if global_:
		target = _resolve_home() / ".claude" / config_mod.CONFIG_FILENAME
	else:
		target = Path(cwd) / config_mod.CONFIG_FILENAME
	try:
		config_mod.write_default_config(target, force=force)
	except FileExistsError:
		raise click.ClickException(
			f"{target} already exists. Re-run with --force to overwrite."
		)
	click.echo(f"wrote {target}")


@main.command("install-skill")
def install_skill_cmd():
	"""Install the skill and /translate command into ~/.claude/."""
	source_root = install_mod.locate_source_root()
	written = install_mod.install(source_root=source_root, target_home=_resolve_home())
	click.echo(json.dumps({"written": written}, indent=2))


@main.command("uninstall-skill")
def uninstall_skill_cmd():
	"""Remove the skill and /translate command from ~/.claude/."""
	removed = install_mod.uninstall(target_home=_resolve_home())
	click.echo(json.dumps({"removed": removed}, indent=2))


@main.group(short_help="NVDA add-on manifest translation.")
def nvda():
	"""NVDA add-on manifest translation (optional; install with [nvda] extra)."""


@nvda.command("scan")
@click.argument("lang")
@click.option("--cwd", type=click.Path(exists=True, file_okay=False), default=".")
def nvda_scan(lang, cwd):
	"""Enumerate pending NVDA manifest translations for <lang>. Emits JSON."""
	root = Path(cwd)
	info = nvda_mod.detect(root)
	if info is None:
		raise click.ClickException("not an NVDA add-on (no manifest.ini found)")
	try:
		out = nvda_mod.scan_manifest(root, lang, info)
	except RuntimeError as e:
		raise click.ClickException(str(e))
	click.echo(json.dumps(out, indent=2))


@nvda.command("apply")
@click.argument("lang")
@click.option("--cwd", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--input", "input_path", default="-")
def nvda_apply(lang, cwd, input_path):
	"""Write NVDA manifest translations for <lang> from JSON payload."""
	raw = sys.stdin.buffer.read().decode("utf-8") if input_path == "-" else Path(input_path).read_text(encoding="utf-8")
	payload = json.loads(raw)
	root = Path(cwd)
	info = nvda_mod.detect(root)
	if info is None:
		raise click.ClickException("not an NVDA add-on (no manifest.ini found)")
	try:
		out = nvda_mod.apply_manifest(root, lang, payload["translations"], info)
	except RuntimeError as e:
		raise click.ClickException(str(e))
	click.echo(json.dumps(out, indent=2))


@main.group(short_help="Markdown / doc file translation.")
def files():
	"""Markdown / doc file translation driven by [[translate_files]] config."""


def _resolve_files_entries(root: Path) -> tuple[list, dict | None, str]:
	"""Return (entries, nvda_info, source_lang) for a files command."""
	cfg = config_mod.load_config(root)
	det = project.detect(root)
	entries = files_mod.effective_entries(cfg.translate_files, det["nvda"])
	source_lang = det["source_lang"] or "en"
	return entries, det["nvda"], source_lang


@files.command("scan")
@click.argument("lang")
@click.option("--cwd", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--force", is_flag=True, default=False,
			  help="Include files whose target already exists (they will be overwritten on apply).")
def files_scan(lang, cwd, force):
	"""Enumerate pending doc-file translations for <lang>. Emits JSON."""
	root = Path(cwd).resolve()
	entries, _nvda_info, source_lang = _resolve_files_entries(root)
	if not entries:
		click.echo(json.dumps({
			"project": {"source_lang": source_lang, "target_lang": lang},
			"entries": [],
		}, indent=2))
		return
	out = files_mod.scan_files(root, entries, source_lang, lang, force=force)
	click.echo(json.dumps(out, indent=2))


@files.command("apply")
@click.argument("lang")
@click.option("--cwd", type=click.Path(exists=True, file_okay=False), default=".")
@click.option("--input", "input_path", default="-")
@click.option("--force", is_flag=True, default=False,
			  help="Overwrite existing target files.")
def files_apply(lang, cwd, input_path, force):
	"""Write translated doc files for <lang> from JSON payload."""
	raw = sys.stdin.buffer.read().decode("utf-8") if input_path == "-" else Path(input_path).read_text(encoding="utf-8")
	payload = json.loads(raw)
	root = Path(cwd).resolve()
	entries, _nvda_info, source_lang = _resolve_files_entries(root)
	if not entries:
		click.echo(json.dumps({
			"summary": {"written_ok": 0, "verification_failed": 0, "skipped": 0},
			"entries": [],
		}, indent=2))
		return
	out = files_mod.apply_files(
		root, entries, source_lang, lang,
		payload.get("translations", []),
		force=force,
	)
	click.echo(json.dumps(out, indent=2))


if __name__ == "__main__":
	main()
