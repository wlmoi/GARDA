"""HTTP integration checks; no physical device access or FPGA programming."""
import http.client
import importlib.util
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / 'scripts/mock_dashboard.py'
spec = importlib.util.spec_from_file_location('dashboard_under_test', path)
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = dashboard.ThreadingHTTPServer(('127.0.0.1', 0), dashboard.Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def request(self, method, url, data=None, token=False):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        headers = {'X-GARDA-Token': dashboard.TOKEN} if token else {}
        connection.request(method, url, json.dumps(data) if data is not None else None, headers)
        response = connection.getresponse()
        code, body = response.status, response.read().decode()
        connection.close()
        return code, body

    def test_home_and_all_launch_buttons(self):
        code, html = self.request('GET', '/')
        self.assertEqual(code, 200)
        self.assertIn(dashboard.TOKEN, html)
        for key in dashboard.TESTS:
            self.assertIn('data-test="' + key + '"', html)

    def test_start_requires_token(self):
        self.assertEqual(self.request('POST', '/api/run', {'test': 'cargo'})[0], 403)

    def test_unknown_command_cannot_execute(self):
        self.assertEqual(self.request('POST', '/api/run', {'test': 'arbitrary command'}, True)[0], 400)

    def test_busy_port_slot_rejects_second_job(self):
        with dashboard.LOCK:
            dashboard.STATE['running'] = True
        try:
            self.assertEqual(self.request('POST', '/api/run', {'test': 'cargo'}, True)[0], 409)
        finally:
            with dashboard.LOCK:
                dashboard.STATE['running'] = False

    def test_file_cannot_escape_evidence(self):
        self.assertEqual(self.request('GET', '/api/file?path=../README.md')[0], 404)
        self.assertEqual(self.request('GET', '/api/file?path=scripts/mock_dashboard.py')[0], 404)

    def test_start_dispatches_fixed_job(self):
        dispatched = threading.Event()
        with patch.object(dashboard, 'run_job', side_effect=lambda key: dispatched.set()) as job:
            self.assertEqual(self.request('POST', '/api/run', {'test': 'cargo'}, True)[0], 200)
            self.assertTrue(dispatched.wait(2))
            job.assert_called_once_with('cargo')
        with dashboard.LOCK:
            dashboard.STATE['running'] = False


if __name__ == '__main__':
    unittest.main()
