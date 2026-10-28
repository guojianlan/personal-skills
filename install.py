#!/usr/bin/env python3
"""Install the personal Skills collection without copying credentials."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def install():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills-dir", type=Path, help="Defaults to CODEX_HOME/skills or ~/.codex/skills")
    parser.add_argument("--skip-mcp", action="store_true", help="Install only the Skill")
    parser.add_argument("--skill", action="append", choices=["github-notes", "github-resources"],
                        help="Install selected Skill(s); defaults to both")
    args = parser.parse_args()
    selected = args.skill or ["github-notes", "github-resources"]
    register_mcp = "github-notes" in selected and not args.skip_mcp
    if sys.version_info < (3, 9):
        parser.error("Python 3.9 or newer is required")
    gh = shutil.which("gh")
    if not gh:
        parser.error("Install GitHub CLI first: https://cli.github.com/")
    codex = shutil.which("codex")
    if register_mcp and not codex:
        parser.error("Codex CLI is required for registration; use --skip-mcp for manual MCP setup")
    base = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    skills_dir = (args.skills_dir or base / "skills").expanduser().resolve()
    target = skills_dir / "github-notes"
    script = target / "scripts" / "github_notes.py"
    existing = None
    if register_mcp:
        result = subprocess.run([codex, "mcp", "get", "github-notes", "--json"], capture_output=True, text=True, timeout=20)
        if result.returncode == 0:
            existing = json.loads(result.stdout)
            transport = existing.get("transport", {})
            if transport.get("command") != sys.executable or transport.get("args") != [str(script), "stdio"]:
                parser.error("An unrelated github-notes MCP entry already exists. Inspect it before replacing it.")
    installed = []
    for name in dict.fromkeys(selected):
        source = Path(__file__).resolve().parent / "skills" / name
        destination = skills_dir / name
        if source == destination:
            parser.error("Run the installer from its checkout, outside the installed Skill directory")
        if destination.exists():
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            backup = base / "backups" / (name + "-skill-" + stamp)
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(destination, backup)
        shutil.copytree(source, destination, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        installed.append(str(destination))
    if register_mcp and existing is None:
        # Let Codex preserve its own config schema and unrelated settings.
        config = base / "config.toml"
        if config.exists():
            backup = base / "backups" / ("before-github-notes-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".toml")
            backup.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(str(backup), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(config.read_bytes())
        subprocess.run([codex, "mcp", "add", "github-notes", "--env", "GITHUB_NOTES_GH=" + gh,
                        "--", sys.executable, str(script), "stdio"], check=True, timeout=30)
    print(json.dumps({"skill": str(target) if "github-notes" in selected else installed[0],
                      "skills": installed, "mcp_registered": register_mcp,
                      "authentication": "Use gh auth login on each computer; no credentials were copied.",
                      "other_clients": {"mcpServers": {"github-notes": {"command": sys.executable,
                                        "args": [str(script), "stdio"], "env": {"GITHUB_NOTES_GH": gh}}}} if "github-notes" in selected else {},
                      "next": "Start a new Codex chat/client session. Installed: " + ", ".join(selected)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    install()
