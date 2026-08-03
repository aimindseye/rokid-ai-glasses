#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


c = load('persistent111', 'collect_test21_r3_3_4_2_5_2_1_1_1_persistent.py')


class T(unittest.TestCase):
    def test_remote_command_is_single_quoted_su_c(self):
        script = "printf 'WORKER_READY\\n'\nprintf '%s\\n' \"a'b\"\n"
        cmd = c.build_remote_worker_command(script)
        self.assertTrue(cmd.startswith('su -c '))
        self.assertNotIn('su -c sh', cmd)
        self.assertNotEqual(cmd, 'su -c ' + script)

    def test_short_47_bytes_not_credited(self):
        self.assertEqual(c.trusted_prefix_length(47, 8 * 1024 * 1024), 0)

    def test_139264_partial_credits_34_pages(self):
        self.assertEqual(c.trusted_prefix_length(139264, 8 * 1024 * 1024), 139264)
        self.assertEqual(139264 // c.PAGE, 34)

    def test_plan_is_page_aligned(self):
        rows = [{'start': 0x1000, 'end': 0x1000 + 100000, 'size': 100000, 'perms': 'rw-p', 'path': ''}]
        plan = c.plan_chunks(rows, chunk_size=65536, max_total=131072)
        self.assertTrue(plan)
        for row in plan:
            self.assertEqual(row['start'] % c.PAGE, 0)
            self.assertEqual(row['size'] % c.PAGE, 0)

    def test_worker_script_supports_protocol_gate_and_cleanup(self):
        self.assertIn('/data/local/tmp/rokid-test21-r32521111-$$', c.WORKER_SCRIPT)
        self.assertIn('trap cleanup_worker 0 1 2 15', c.WORKER_SCRIPT)
        self.assertIn('PING)', c.WORKER_SCRIPT)
        self.assertIn("printf 'PONG\\n'", c.WORKER_SCRIPT)
        self.assertIn('dd if="/proc/$a/mem"', c.WORKER_SCRIPT)
        self.assertIn('BYE|%s', c.WORKER_SCRIPT)

    def test_rootworker_source_uses_shell_t_not_exec_out(self):
        s = (HERE / 'collect_test21_r3_3_4_2_5_2_1_1_1_persistent.py').read_text()
        self.assertIn("[adb, '-s', phone, 'shell', '-T', remote_command]", s)
        self.assertNotIn("'exec-out', 'su', '-c', 'sh'", s)
        self.assertNotIn("[adb, '-s', phone, 'shell', '-T', 'su', '-c'", s)
        self.assertIn("return 'su -c ' + shlex.quote(worker_script)", s)

    def test_real_nontty_bidirectional_fake_adb_transport(self):
        # Exercise the exact host-side shape: adb shell -T "su -c '<worker>'".
        # A fake adb and fake su let this run without a phone while preserving
        # quoting and bidirectional stdin/stdout semantics.
        worker = r'''printf 'WORKER_READY\n'
emit() {
  req="$1"; text="$2"
  n=$(printf '%s' "$text" | wc -c | tr -d ' ')
  printf 'FRAME|%s|0|%s|0\n' "$req" "$n"
  printf '%s' "$text"
  printf '\nEND|%s\n' "$req"
}
while IFS='|' read -r op req a b c; do
  case "$op" in
    ID) emit "$req" 'uid=0(root) gid=0(root)' ;;
    PING) emit "$req" 'PONG' ;;
    QUIT) printf 'BYE|%s\n' "$req"; exit 0 ;;
    *) emit "$req" '' ;;
  esac
done
'''
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            adb = td / 'adb'
            su = td / 'su'
            adb.write_text("""#!/bin/sh
if [ \"$1\" = \"-s\" ]; then shift 2; fi
if [ \"$1\" = \"shell\" ] && [ \"$2\" = \"-T\" ]; then
  shift 2
  exec /bin/sh -c \"$1\"
fi
exit 91
""")
            su.write_text("""#!/bin/sh
[ \"$1\" = \"-c\" ] || exit 64
[ -n \"$2\" ] || exit 65
exec /bin/sh -c \"$2\"
""")
            adb.chmod(0o755); su.chmod(0o755)
            old_path = os.environ.get('PATH', '')
            os.environ['PATH'] = str(td) + os.pathsep + old_path
            try:
                w = c.RootWorker(str(adb), 'FAKE', worker_script=worker)
                ident = w.request('ID', [], 3)
                self.assertEqual(ident['rc'], 0)
                self.assertIn(b'uid=0(root)', ident['payload'])
                ping = w.request('PING', [], 3)
                self.assertEqual(ping['payload'], b'PONG')
                w.close()
                self.assertTrue(w.cleanup_reported)
            finally:
                os.environ['PATH'] = old_path

    def test_main_has_id_ping_gate_before_maps(self):
        s = (HERE / 'collect_test21_r3_3_4_2_5_2_1_1_1_persistent.py').read_text()
        i_id = s.index("worker.request('ID'")
        i_ping = s.index("worker.request('PING'")
        i_maps = s.index("worker.request('MAPS'")
        self.assertLess(i_id, i_ping)
        self.assertLess(i_ping, i_maps)
        self.assertIn("PERSISTENT_ROOT_SESSION_QUALIFICATION=PASS", s)
        self.assertIn("MAGISK_SU_COMMAND_QUOTING=PASS", s)

    def test_prior_signature_regression(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / 'private/external-memory'
            p.mkdir(parents=True)
            manifest = [
                {'chunk': i, 'bytes_read': 47, 'read_status': 'PARTIAL', 'chunk_sha256': 'a' * 64}
                for i in range(31)
            ]
            manifest.append({'chunk': 31, 'bytes_read': 139264, 'read_status': 'PARTIAL', 'chunk_sha256': 'b' * 64})
            (p / 'external-memory-private.json').write_text(json.dumps({
                'selected_bytes': 268435456,
                'memory_bytes_read': 140721,
                'manifest': manifest,
            }))
            x = c.characterize_prior(str(root))
            self.assertEqual(x['returned_size_mode_bytes'], 47)
            self.assertEqual(x['returned_size_mode_count'], 31)
            self.assertEqual(x['duplicate_short_output_max_count'], 31)

    def test_runner_no_injection_or_connection_mutation(self):
        s = (HERE / 'run_test21_r3_3_4_2_5_2_1_1_1_resume.sh').read_text()
        for bad in ['force-stop', 'am start', 'monkey ', ' pm clear', 'svc bluetooth', 'set -e', 'set -u', 'set -o pipefail']:
            self.assertNotIn(bad, s)
        for required in ['FRIDA_PROCESS_ATTACH=NONE', 'PTRACE_ATTACH=NONE', 'PROCESS_SIGNAL=NONE']:
            self.assertIn(required, s)

    def test_analyzer_cannot_exhaust_partial_coverage(self):
        s = (HERE / 'analyze_test21_r3_3_4_2_5_2_1_1_1_bootstrap.py').read_text()
        self.assertIn('elif not census_exhausted:', s)
        self.assertIn('SELECTED_MEMORY_CENSUS_INCOMPLETE_TARGET_NOT_FOUND_IN_RECOVERED_RANGES', s)
        self.assertIn('target_absence_from_process_memory_proven', s)
        self.assertIn('persistent_root_session_qualification', s)

    def test_packager_excludes_private_material(self):
        s = (HERE / 'package_test21_r3_3_4_2_5_2_1_1_1_sanitized.py').read_text()
        self.assertIn('COVERAGE_SEGMENTS_INCLUDED=NO', s)
        self.assertIn('RECOVERED_DEX_INCLUDED=NO', s)
        self.assertNotIn('external-memory-persistent-bootstrap-private.json', s)


if __name__ == '__main__':
    unittest.main(verbosity=2)
