import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CHECKER = Path(__file__).resolve().parents[1] / 'scripts/check-vpn.sh'
APPROVED = '207.90.237.248'


class VpnGuardTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.allowed = self.root / 'allowed.txt'
        self.allowed.write_text(APPROVED + '\n')
        self.log = self.root / 'checks.log'
        self.calls = self.root / 'calls.jsonl'
        self.environment = os.environ | {
            'PATH': str(self.root) + os.pathsep + os.environ['PATH'],
            'VPN_GUARD_ALLOWED_IPS_FILE': str(self.allowed),
            'VPN_GUARD_LOG_FILE': str(self.log),
            'VPN_TEST_CALLS': str(self.calls),
            'VPN_TEST_CLOCK': str(self.root / 'clock'),
            'VPN_TEST_REPLIES': '[]',
        }
        self.environment.pop('VPN_TEST_TICKS', None)
        self.executable('curl', '''
import json, os, sys
from pathlib import Path
p = Path(os.environ['VPN_TEST_CALLS'])
calls = p.read_text().splitlines() if p.exists() else []
replies = json.loads(os.environ['VPN_TEST_REPLIES'])
reply = replies[len(calls)]
with p.open('a') as f: f.write(json.dumps(sys.argv[1:]) + '\\n')
sys.stdout.write(reply.get('body', ''))
sys.stderr.write(reply.get('error', ''))
sys.exit(reply.get('code', 0))
''')
        self.executable('date', '''
import json, os, sys
from pathlib import Path
if sys.argv[1:] == ['+%s'] and 'VPN_TEST_TICKS' in os.environ:
    p = Path(os.environ['VPN_TEST_CLOCK'])
    index = int(p.read_text()) if p.exists() else 0
    ticks = json.loads(os.environ['VPN_TEST_TICKS'])
    p.write_text(str(index + 1))
    print(ticks[min(index, len(ticks) - 1)])
else:
    os.execv('/bin/date', ['date', *sys.argv[1:]])
''')

    def executable(self, name, body):
        path = self.root / name
        path.write_text('#!' + sys.executable + '\n' + body)
        path.chmod(0o755)

    def run_check(self, replies):
        self.environment['VPN_TEST_REPLIES'] = json.dumps(replies)
        result = subprocess.run(
            [os.environ.get('VPN_TEST_SHELL', '/bin/sh'), str(CHECKER)],
            env=self.environment, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.stdout, '')
        return result

    def requests(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def test_approved_first_lookup_is_silent(self):
        result = self.run_check([{'body': APPROVED}])
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        self.assertFalse(self.log.exists())
        self.assertEqual(len(self.requests()), 1)
        self.assertIn('--ipv4', self.requests()[0])
        self.assertIn('=https', self.requests()[0])

    def test_dns_failure_recovers_with_independent_fallback(self):
        result = self.run_check([{'code': 6, 'error': 'Could not resolve host: api.ipify.org'}, {'body': APPROVED + '\n'}])
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        self.assertEqual([call[-1] for call in self.requests()], ['https://api.ipify.org', 'https://checkip.amazonaws.com'])
        log = self.log.read_text()
        self.assertIn('curl_exit=6 Could not resolve host', log)
        self.assertIn('recovered attempt=2', log)

    def test_two_failures_retry_primary_once(self):
        result = self.run_check([{'code': 28, 'error': 'timeout'}, {'code': 35, 'error': 'TLS failure'}, {'body': APPROVED}])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(self.requests()), 3)
        self.assertEqual(self.requests()[-1][-1], 'https://api.ipify.org')
        self.assertIn('recovered attempt=3', self.log.read_text())

    def test_all_lookup_failures_block_with_diagnostics(self):
        result = self.run_check([{'code': 6, 'error': 'DNS'}, {'code': 28, 'error': 'timeout'}, {'code': 35, 'error': 'TLS'}])
        self.assertEqual(result.returncode, 2)
        self.assertIn('after 3 attempts', result.stderr)
        self.assertIn(str(self.log), result.stderr)
        self.assertEqual(len(self.requests()), 3)
        for code in (6, 28, 35):
            self.assertIn(f'curl_exit={code}', self.log.read_text())

    def test_unapproved_ip_blocks_without_fallback(self):
        result = self.run_check([{'body': '8.8.8.8'}, {'body': APPROVED}])
        self.assertEqual(result.returncode, 2)
        self.assertIn('public IP 8.8.8.8 is not allowed', result.stderr)
        self.assertEqual(len(self.requests()), 1)

    def test_unapproved_fallback_blocks_without_third_attempt(self):
        result = self.run_check([{'code': 6}, {'body': '8.8.8.8'}, {'body': APPROVED}])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(len(self.requests()), 2)

    def test_malformed_replies_cannot_match_allowlist(self):
        for body in ('', 'garbage', '207.90.237.248\n207.90.237.248', '207.90.237.999', '0207.90.237.248', '2001:4860::1'):
            with self.subTest(body=body):
                self.calls.unlink(missing_ok=True)
                self.allowed.write_text(body + '\n')
                result = self.run_check([{'body': body}] * 3)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(len(self.requests()), 3)
                self.assertIn('invalid IPv4 response', self.log.read_text())

    def test_missing_settings_block_before_network(self):
        self.allowed.unlink()
        result = self.run_check([])
        self.assertEqual(result.returncode, 2)
        self.assertIn('cannot read settings', result.stderr)
        self.assertFalse(self.calls.exists())

    def test_remaining_deadline_caps_request_and_rejects_late_success(self):
        self.environment['VPN_TEST_TICKS'] = json.dumps([100, 100, 101, 109, 110])
        result = self.run_check([{'code': 6}, {'body': APPROVED}])
        self.assertEqual(result.returncode, 2)
        calls = self.requests()
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1][calls[1].index('--max-time') + 1], '1')
        self.assertIn('deadline exceeded', self.log.read_text())

    def test_expired_deadline_starts_no_more_requests(self):
        self.environment['VPN_TEST_TICKS'] = json.dumps([100, 100, 101, 110])
        result = self.run_check([{'code': 6}])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(len(self.requests()), 1)

    def test_unwritable_log_cannot_change_verdict(self):
        self.environment['VPN_GUARD_LOG_FILE'] = '/dev/null/blocked.log'
        result = self.run_check([{'code': 6}, {'body': APPROVED}])
        self.assertEqual((result.returncode, result.stderr), (0, ''))


if __name__ == '__main__':
    unittest.main()
