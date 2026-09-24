#!/usr/bin/env python3
"""Install a private local runtime and plugin. Excludes credentials from the package."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent

def run(*args):
    subprocess.run([str(a) for a in args], check=True)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--plugin-skill', type=Path, required=True, help='Path to plugin-creator skill')
    a = p.parse_args()
    home = Path.home()
    target = home/'plugins/telegram-mcp'
    if target.exists():
        raise SystemExit('Plugin source already exists; update it using the plugin-creator update workflow.')
    runtime = home/'.local/share/telegram-mcp/venv'
    if not (runtime/'bin/python').exists():
        run(sys.executable, '-m', 'venv', runtime)
    run(runtime/'bin/python', '-m', 'pip', 'install', '-r', ROOT/'requirements.lock')
    # Scaffold handles the personal marketplace contract; preserve the resulting entry.
    run(sys.executable, a.plugin_skill/'scripts/create_basic_plugin.py', 'telegram-mcp', '--with-marketplace')
    for rel in ['src', 'scripts', 'skills', '.codex-plugin']:
        shutil.copytree(ROOT/rel, target/rel, dirs_exist_ok=True)
    for rel in ['plugin.json', '.mcp.json', 'mcp.json', 'pyproject.toml', 'requirements.lock', 'README.md']:
        shutil.copy2(ROOT/rel, target/rel)
    config = home/'.config/telegram-mcp/config.json'
    if not config.exists():
        run(sys.executable, ROOT/'scripts/setup.py', 'import', '--source', ROOT/'.local', '--config', config, '--credentials-name', 'config.json', '--session-name', 'telegram.session')
    marketplace = json.loads((home/'.agents/plugins/marketplace.json').read_text())['name']
    run('codex', 'plugin', 'add', 'telegram-mcp@'+marketplace)
    print('Installed Telegram plugin; configuration remains outside the plugin cache.')

if __name__ == '__main__':
    main()
