"""Run active-source failure contracts on Windows; no physical motor or cable claims."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


class LaptopFaultContracts(unittest.TestCase):
    def test_real_controller_fault_handler_only_sends_four_zeros_and_returns(self):
        source = ROOT / 'src/igor_controller/igor_controller/controller_node.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'IgorControllerNode')
        control = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == '_control_loop')
        handler = next(n for n in ast.walk(control) if isinstance(n, ast.ExceptHandler) and isinstance(n.type, ast.Name) and n.type.id == 'FPGACommunicationError')
        wrapper = ast.parse('def exercise(self):\n try:\n  raise FPGACommunicationError("injected link loss")\n except FPGACommunicationError as exc:\n  pass\n self.nonzero_path()\n')
        wrapper.body[0].body[0].handlers[0] = copy.deepcopy(handler)
        ast.fix_missing_locations(wrapper)
        class FPGACommunicationError(RuntimeError):
            pass
        context = dict(FPGACommunicationError=FPGACommunicationError, json=json,
                       Twist=lambda: SimpleNamespace(zero=True), Bool=lambda **kw: kw, String=lambda **kw: kw)
        exec(compile(wrapper, str(source) + ':FPGACommunicationError handler', 'exec'), context)
        motors, velocities, alerts, diagnostics = [], [], [], []
        target = SimpleNamespace(
            mcu=SimpleNamespace(send_motor_speeds=lambda *values: motors.append(values)),
            pub_safe_twist=SimpleNamespace(publish=velocities.append),
            pub_safety_alert=SimpleNamespace(publish=alerts.append),
            pub_diag=SimpleNamespace(publish=diagnostics.append),
            get_logger=lambda: SimpleNamespace(error=lambda text: None),
            nonzero_path=lambda: self.fail('Normal actuation continued after fault'))
        context['exercise'](target)
        self.assertEqual(motors, [(0., 0., 0., 0.)])
        self.assertEqual(len(velocities), 1)
        self.assertEqual(alerts, [{'data': True}])
        report = json.loads(diagnostics[0]['data'])
        self.assertFalse(report['safety_permit'])
        self.assertTrue(report['fault'].startswith('FPGA_TRANSPORT'))

    def test_transport_latch_rejects_retries_before_serial_access(self):
        source = ROOT / 'src/igor_controller/igor_controller/fpga_bridge.py'
        spec = importlib.util.spec_from_file_location('laptop_bridge', source)
        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)
        target = bridge.FPGABridge.__new__(bridge.FPGABridge)
        target._fault_latched = True
        target.last_exchange_ok = True
        # Deliberately no serial connection attributes: any IO attempt would fail.
        for _ in range(3):
            with self.assertRaisesRegex(bridge.FPGACommunicationError, 'latched'):
                target.infer(np.zeros(74))
            self.assertFalse(target.last_exchange_ok)


if __name__ == '__main__':
    unittest.main()
