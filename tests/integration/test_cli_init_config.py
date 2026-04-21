import os
import subprocess
from pathlib import Path

from gettext_auto.config import CONFIG_FILENAME, DEFAULT_TEMPLATE


def _run(*args, cwd, env=None):
	return subprocess.run(
		["gettext-auto", *args], cwd=str(cwd),
		capture_output=True, text=True, check=False, env=env,
	)


def test_init_config_writes_to_cwd(tmp_path):
	r = _run("init-config", cwd=tmp_path)
	assert r.returncode == 0, r.stderr
	target = tmp_path / CONFIG_FILENAME
	assert target.is_file()
	assert target.read_text(encoding="utf-8") == DEFAULT_TEMPLATE
	assert CONFIG_FILENAME in r.stdout


def test_init_config_refuses_existing(tmp_path):
	target = tmp_path / CONFIG_FILENAME
	target.write_text("existing", encoding="utf-8")
	r = _run("init-config", cwd=tmp_path)
	assert r.returncode != 0
	assert "--force" in r.stderr or "--force" in r.stdout
	assert target.read_text(encoding="utf-8") == "existing"


def test_init_config_force_overwrites(tmp_path):
	target = tmp_path / CONFIG_FILENAME
	target.write_text("existing", encoding="utf-8")
	r = _run("init-config", "--force", cwd=tmp_path)
	assert r.returncode == 0, r.stderr
	assert target.read_text(encoding="utf-8") == DEFAULT_TEMPLATE


def test_init_config_global_writes_to_home(tmp_path):
	home = tmp_path / "home"
	home.mkdir()
	env = dict(os.environ)
	env["USERPROFILE"] = str(home)
	env["HOME"] = str(home)
	cwd = tmp_path / "proj"
	cwd.mkdir()
	r = _run("init-config", "--global", cwd=cwd, env=env)
	assert r.returncode == 0, r.stderr
	target = home / ".claude" / CONFIG_FILENAME
	assert target.is_file()
	assert target.read_text(encoding="utf-8") == DEFAULT_TEMPLATE
	# And NOT in the project directory.
	assert not (cwd / CONFIG_FILENAME).exists()
