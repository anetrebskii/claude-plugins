#!/usr/bin/env python3
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

SEPARATOR = r'(?:[ \t]*(?:\\n|\r?\n))*[ \t]*'
COAUTHOR = r'co-authored-by:[^\r\n<>]*<[^\r\n<>]*>'
CLAUDE = r'(?:\[Claude(?: Code)?\]\(https://(?:claude\.(?:com|ai)|(?:www\.)?anthropic\.com)/[^\s)"\x27]*\)|Claude Code\b|Claude\b)'
FOOTER = rf'(?:🤖[ \t]*)?(?:generated|created|written|authored|powered)[ \t]+(?:with|by|using)[ \t]+{CLAUDE}'
SESSION = r'Claude-Session:[ \t]*https://claude\.ai/code/session_[A-Za-z0-9_-]+'
ATTRIBUTION = re.compile(SEPARATOR + rf'(?P<text>{COAUTHOR}|{FOOTER}|{SESSION})[ \t]*', re.I)
FILE_ARG = re.compile(r'''(?P<flag>--body-file|--file|-F)(?P<separator>=|[ \t]+)(?P<path>'[^']*'|"[^"$`]*"|[^\s"';&|<>]+)''')


def clean(text):
    def remove(match):
        value = match['text']
        if value.lower().startswith('co-authored-by:') and not re.search(r'\b(?:claude|anthropic)\b', value, re.I):
            return match[0]
        return ''
    return ATTRIBUTION.sub(remove, text)


def output(updated, previous=None):
    result = previous or {'hookSpecificOutput': {'hookEventName': 'PreToolUse'}}
    result['hookSpecificOutput']['updatedInput'] = updated
    print(json.dumps(result))


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--clean-file':
        sys.stdout.write(clean(Path(sys.argv[2]).read_text()))
        return
    payload = json.load(sys.stdin)
    original = payload.get('tool_input', {})
    tool_input = dict(original)
    previous = None
    rtk_hook = os.environ.get('CLAUDE_PLUGIN_OPTION_RTK_HOOK', '')
    if len(sys.argv) == 3 and sys.argv[1] == '--rtk-hook':
        rtk_hook = sys.argv[2]
    if rtk_hook:
        result = subprocess.run(['bash', rtk_hook], input=json.dumps(payload), text=True, capture_output=True)
        if result.returncode == 0 and result.stdout.strip():
            previous = json.loads(result.stdout)
            tool_input.update(previous.get('hookSpecificOutput', {}).get('updatedInput', {}))
    name = payload.get('tool_name', '')
    if name == 'Bash':
        command = tool_input.get('command', '')
        writing = re.search(r'\bgit\b[^\n;&|]*\b(?:commit|tag)\b|\bgh\b[^\n;&|]*\b(?:create|edit|comment|api|merge)\b', command)
        if not writing or re.match(r'\s*(?:grep|rg)\s', command) or '--grep' in command:
            if previous:
                print(json.dumps(previous))
            return
        cleaned = clean(command)
        def clean_file(match):
            path = shlex.split(match['path'])[0]
            if path == '-' or re.search(r'[$`\\]', path):
                return match[0]
            absolute = Path(payload.get('cwd') or os.getcwd()) / path
            try:
                content = absolute.read_text()
            except (OSError, UnicodeError):
                return match[0]
            if clean(content) == content:
                return match[0]
            helper = shlex.quote(str(Path(__file__).resolve()))
            return f"{match['flag']} <(python3 {helper} --clean-file {shlex.quote(str(absolute))})"
        cleaned = FILE_ARG.sub(clean_file, cleaned)
        cleaned = re.sub(r'''[ \t]*(?:-m|--message|--trailer)[ \t]+(?:""|'')''', '', cleaned)
        if cleaned != command:
            message = r'(^|\s)(-m|--message|-F|--file|-c|-C|-t|--template|--amend)([\s=]|$)|<<'
            if not cleaned.strip() or (re.search(message, command) and not re.search(message, cleaned)):
                print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny', 'permissionDecisionReason': 'Attribution was the entire commit message. Retry with a descriptive message without Claude attribution.'}}))
                return
            tool_input['command'] = cleaned
    elif re.search(r'(?:^|__)github(?:__|_).*', name, re.I) and re.search(r'(?:create|update|edit|add|push|merge)', name):
        for key in ('body', 'message', 'commit_message'):
            if isinstance(tool_input.get(key), str):
                tool_input[key] = clean(tool_input[key])
    if tool_input != original:
        output(tool_input, previous)
    elif previous:
        print(json.dumps(previous))


if __name__ == '__main__':
    main()
