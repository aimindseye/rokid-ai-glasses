#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / 'scripts/tests/test22_wifi_state.py'
spec = importlib.util.spec_from_file_location('test22_wifi_state', PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class WifiStateTests(unittest.TestCase):
    def test_actual_glasses_off_state(self):
        self.assertEqual(mod.classify('0\r\n', 'error: closed\n'), 'DISABLED')

    def test_settings_on_wins_over_unhelpful_cmd(self):
        self.assertEqual(mod.classify('1\n', ''), 'ENABLED')

    def test_cmd_fallback_disabled(self):
        self.assertEqual(mod.classify('null\n', 'WiFi is disabled\n'), 'DISABLED')

    def test_cmd_fallback_enabled(self):
        self.assertEqual(mod.classify('', 'Wifi is enabled\n'), 'ENABLED')

    def test_unknown_is_bounded(self):
        self.assertEqual(mod.classify('null', 'unrecognized platform response'), 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()
