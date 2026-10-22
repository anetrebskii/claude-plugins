import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

HOOK = Path(__file__).resolve().parents[1] / 'scripts/strip-coauthor.sh'
TRAILER = 'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'
HUMAN = 'Co-Authored-By: Dev <dev@example.com>'
FOOTER = '🤖 Generated with [Claude Code](https://claude.com/claude-code)'
SESSION = 'Claude-Session: https://claude.ai/code/session_013noRUruiCgJVn5GwVYKMx5'


class HookTest(unittest.TestCase):
    def run_hook(self, command, cwd=None, tool='Bash', extra=None, args=()):
        tool_input = {'command': command, 'description': 'keep', 'timeout': 1000, 'run_in_background': False}
        if extra is not None:
            tool_input = extra
        payload = {'tool_name': tool, 'tool_input': tool_input, 'cwd': str(cwd or Path.cwd())}
        result = subprocess.run(['bash', str(HOOK), *args], input=json.dumps(payload), text=True, capture_output=True, check=True)
        output = json.loads(result.stdout) if result.stdout.strip() else {}
        updated = output.get('hookSpecificOutput', {}).get('updatedInput', tool_input)
        if output and 'updatedInput' in output['hookSpecificOutput']:
            self.assertEqual({k: v for k, v in updated.items() if k != 'command'}, {k: v for k, v in tool_input.items() if k != 'command'} if extra is None else {k: (v if k != 'body' else updated[k]) for k, v in tool_input.items()})
        return updated.get('command'), output

    def test_actual_pr_commit(self):
        cmd = 'git commit -F- <<\'EOF\'\n#3257 Update the Recall desktop SDK to 2.0.40\n\n' + TRAILER + '\n' + SESSION + '\nEOF'
        updated, _ = self.run_hook(cmd)
        self.assertEqual(updated, "git commit -F- <<'EOF'\n#3257 Update the Recall desktop SDK to 2.0.40\nEOF")

    def test_mixed_coauthors(self):
        for trailers in [HUMAN + '\n' + TRAILER, TRAILER + '\n' + HUMAN]:
            updated, _ = self.run_hook('git commit -m ' + shlex.quote('fix\n\n' + trailers))
            self.assertIn(HUMAN, updated)
            self.assertNotIn(TRAILER, updated)

    def test_footers(self):
        for footer in [FOOTER, 'Generated with Claude Code', 'Created by Claude Code', 'Written using Claude Code', 'Powered by [Claude](https://claude.ai/)']:
            updated, _ = self.run_hook('gh pr create --body ' + shlex.quote('body\n\n' + footer))
            self.assertEqual(updated, "gh pr create --body 'body'")

    def test_escaped_footer(self):
        updated, _ = self.run_hook('gh pr edit 4083 --body "body\\n\\n' + FOOTER + '"')
        self.assertEqual(updated, 'gh pr edit 4083 --body "body"')

    def test_human_email_not_rewritten(self):
        cmd = 'git commit -m ' + shlex.quote('fix\n\n' + HUMAN)
        self.assertEqual(self.run_hook(cmd)[0], cmd)

    def test_model_name_not_required(self):
        updated, _ = self.run_hook('git commit -m ' + shlex.quote('fix\n\nCo-Authored-By: Assistant <noreply@anthropic.com>'))
        self.assertEqual(updated, "git commit -m 'fix'")

    def test_github_tool(self):
        _, output = self.run_hook('', tool='mcp__github__create_pull_request', extra={'body': 'body\n\n' + FOOTER, 'title': 'keep', 'head': 'branch'})
        self.assertEqual(output['hookSpecificOutput']['updatedInput'], {'body': 'body', 'title': 'keep', 'head': 'branch'})
        self.assertNotIn('permissionDecision', output['hookSpecificOutput'])

    def test_real_git_file_and_heredoc(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', directory], check=True)
            env = dict(os.environ, GIT_AUTHOR_NAME='Test', GIT_AUTHOR_EMAIL='test@example.com', GIT_COMMITTER_NAME='Test', GIT_COMMITTER_EMAIL='test@example.com')
            body = 'fix\n\n' + HUMAN + '\n' + TRAILER + '\n' + SESSION + '\n\n' + FOOTER
            source = root / 'message with spaces.txt'
            source.write_text(body)
            for argument in ['-F ' + shlex.quote(str(source)), '--file=' + shlex.quote(str(source)), "-F- <<'EOF'\n" + body + '\nEOF']:
                updated, _ = self.run_hook('git -c core.hooksPath=/dev/null commit --allow-empty ' + argument, cwd=root)
                subprocess.run(['bash', '-c', updated], cwd=root, env=env, check=True, capture_output=True)
                message = subprocess.check_output(['git', 'log', '-1', '--format=%B'], cwd=root, text=True)
                self.assertIn(HUMAN, message)
                self.assertNotIn(TRAILER, message)
                self.assertNotIn(SESSION, message)
                self.assertNotIn(FOOTER, message)
                self.assertEqual(source.read_text(), body)

    def test_body_file_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'body.md').write_text('body\n\n' + FOOTER)
            fake = root / 'gh'
            fake.write_text('#!/bin/bash\nwhile [ "$#" -gt 0 ]; do if [ "$1" = --body-file ]; then cat "$2"; exit; fi; shift; done\n')
            fake.chmod(0o755)
            updated, _ = self.run_hook('gh pr create --body-file body.md', cwd=root)
            result = subprocess.check_output(['bash', '-c', updated], cwd=root, env=dict(os.environ, PATH=str(root) + ':' + os.environ['PATH']), text=True)
            self.assertEqual(result, 'body')
            self.assertEqual((root / 'body.md').read_text(), 'body\n\n' + FOOTER)

    def test_read_only_command(self):
        command = 'git log --format=' + shlex.quote(FOOTER)
        self.assertEqual(self.run_hook(command)[0], command)

    def test_rtk_sequencing(self):
        with tempfile.TemporaryDirectory() as directory:
            hook = Path(directory) / 'rtk.sh'
            hook.write_text('cat >/dev/null\n' + "printf '%s' " + shlex.quote(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'updatedInput': {'command': 'rtk git commit -m ' + shlex.quote('fix\n\n' + TRAILER)}, 'permissionDecision': 'allow'}})))
            updated, output = self.run_hook('git commit -m ' + shlex.quote('fix\n\n' + TRAILER), args=('--rtk-hook', str(hook)))
            self.assertEqual(updated, "rtk git commit -m 'fix'")
            self.assertEqual(output['hookSpecificOutput']['permissionDecision'], 'allow')


if __name__ == '__main__':
    unittest.main()
