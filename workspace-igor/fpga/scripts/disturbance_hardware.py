"""Real UART inference adapter for synthetic disturbance tests; no motor I/O."""
import json
import datetime as dt
import time
import numpy as np
from types import SimpleNamespace
from usb_serial_roles import fpga_port
import verify_mock_inference as numeric


class HardwareInference:
    def __init__(self, out, host):
        self.path = out / 'physical_fpga_transactions.jsonl'
        self.records = []
        self.port = fpga_port()
        _, self.weights = numeric.load_model()
        for attempt in range(4):
            try:
                self.bridge = host.bridge.FPGABridge(port=self.port, baudrate=921600, timeout=.02, mock=False)
                break
            except Exception as exc:
                if attempt == 3:
                    raise RuntimeError(f'Cannot open FPGA {self.port}: {exc}. Close other UART logger/MobaXterm/test windows, then retry. No mock fallback.') from exc
                print(f'FPGA {self.port} busy/unavailable; retry {attempt+1}/3...', flush=True)
                time.sleep(1)

    def infer(self, obs, stress=False):
        row = dict(timestamp_utc=dt.datetime.now(dt.timezone.utc).isoformat(), port=self.port,
                   observation=list(map(float, obs)), stress_action_injected=stress)
        try:
            actual = self.bridge.infer(obs)
            quantized = np.clip(np.rint(np.asarray(obs) * 256), -32768, 32767).astype(int).tolist()
            expected = numeric.oracle(quantized, self.weights)
            got = np.rint(np.asarray(actual) * 256).astype(int).tolist()
            row.update(expected_q88=expected, actual_q88=got, passed=got == expected)
            if got != expected:
                raise RuntimeError('Physical FPGA output differs from integer oracle')
            # Deliberate post-inference fault injection, never presented as a board result.
            return np.array([1., 0., 0.]) if stress else actual
        except Exception as exc:
            row.update(passed=False, error=str(exc))
            raise
        finally:
            self.records.append(row)
            with self.path.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row) + '\n')

    def attach(self, node, stress=False):
        node.fpga = SimpleNamespace(infer=lambda obs: self.infer(obs, stress))

    def finish(self):
        self.bridge.close()
        if not self.records or not all(r['passed'] for r in self.records):
            raise RuntimeError('Hardware inference absent or failed: no hardware PASS')
        return dict(passed=True, exchanges=len(self.records), port=self.port,
                    evidence=str(self.path), motor_hardware_accessed=False)
