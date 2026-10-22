#!/usr/bin/env python3
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
config = Path(os.environ.get('CLAUDE_CONFIG_DIR', Path.home() / '.claude'))
settings_path = config / 'settings.json'
settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
rtk_path = config / 'hooks/rtk-rewrite.sh'
rtk_commands = {str(rtk_path), '$HOME/.claude/hooks/rtk-rewrite.sh', '~/.claude/hooks/rtk-rewrite.sh'}
rtk_enabled = any(hook.get('command') in rtk_commands for group in settings.get('hooks', {}).get('PreToolUse', []) for hook in group.get('hooks', []))
previous_rtk = settings.get('pluginConfigs', {}).get('no-coauthor@anetrebskii', {}).get('options', {}).get('rtk_hook', '')
if not rtk_enabled and previous_rtk:
    rtk_path = Path(previous_rtk)
    rtk_enabled = True
backup = Path(tempfile.mkdtemp(prefix='no-coauthor-settings-'))
for name in ('settings.json', 'plugins/known_marketplaces.json', 'plugins/installed_plugins.json'):
    source = config / name
    if source.exists():
        destination = backup / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
subprocess.run(['claude', 'plugin', 'marketplace', 'add', str(root), '--json'], check=True)
command = ['claude', 'plugin', 'install', 'no-coauthor@no-coauthor-local', '--scope', 'user', '--json']
if rtk_enabled:
    command += ['--config', 'rtk_hook=' + str(rtk_path)]
subprocess.run(command, check=True)
settings = json.loads(settings_path.read_text())
settings.setdefault('enabledPlugins', {})['no-coauthor@anetrebskii'] = False
settings.setdefault('attribution', {}).update({'commit': '', 'pr': ''})
if rtk_enabled:
    groups = settings.get('hooks', {}).get('PreToolUse', [])
    for group in groups:
        group['hooks'] = [hook for hook in group.get('hooks', []) if hook.get('command') not in rtk_commands]
    settings['hooks']['PreToolUse'] = [group for group in groups if group.get('hooks')]
settings_path.write_text(json.dumps(settings, indent=2) + '\n')
print('Installed from local source; disabled default commit/PR attribution. Restart Claude Code to load the new hook.')
print('Settings and plugin registration backup: ' + str(backup))
