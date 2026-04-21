import shutil
import subprocess
from pathlib import Path


def _run(*args, cwd):
	return subprocess.run(
		["gettext-auto", *args], cwd=str(cwd),
		capture_output=True, text=True, check=False,
	)


def test_scaffold_preview_does_not_write(tmp_path, fixtures_dir):
	proj = tmp_path / "py"
	shutil.copytree(fixtures_dir / "python-no-gettext", proj)
	r = _run("scaffold", "--level", "layout", cwd=proj)
	assert r.returncode == 0, r.stderr
	assert "locale/" in r.stdout
	assert not (proj / "locale").exists()


def test_scaffold_write_creates_layout(tmp_path, fixtures_dir):
	proj = tmp_path / "py"
	shutil.copytree(fixtures_dir / "python-no-gettext", proj)
	r = _run("scaffold", "--level", "layout", "--write", cwd=proj)
	assert r.returncode == 0, r.stderr
	assert (proj / "locale").is_dir()
	assert (proj / "babel.cfg").is_file()
	assert (proj / "locale/README.md").is_file()
