import json
import os
import time
import numpy as np
from igor_controller.fpga_bridge import FPGABridge
from igor_controller.mcu_driver import STM32Driver

trace = open(os.environ['IGOR_INFERENCE_TRACE'], 'x', buffering=1)
original_infer = FPGABridge.infer
original_motor = STM32Driver.send_motor_speeds
sequence = 0

def emit(data):
    data['monotonic_ns'] = time.monotonic_ns()
    trace.write(json.dumps(data, allow_nan=False) + '\n')

def infer(self, observation, *args, **kwargs):
    global sequence
    sequence += 1
    started = time.monotonic_ns()
    record = dict(event='inference', sequence=sequence, endpoint=self.port,
                  started_ns=started, observation=np.asarray(observation).tolist())
    try:
        action = original_infer(self, observation, *args, **kwargs)
        record['observation_q88'] = [int(round(float(v) * 256)) for v in observation]
        record['residual'] = np.asarray(action).tolist()
        record['residual_q88'] = [int(round(float(v) * 256)) for v in action]
        record['ok'] = self.last_exchange_ok
        return action
    except Exception as exc:
        record.update(ok=False, error=str(exc))
        raise
    finally:
        record['elapsed_ms'] = (time.monotonic_ns() - started) / 1e6
        emit(record)

def motor(self, *rps):
    result = original_motor(self, *rps)
    emit(dict(event='motor_send', sequence=sequence,
              rps=list(rps), write_ok=result is True))
    return result

FPGABridge.infer = infer
STM32Driver.send_motor_speeds = motor
from igor_controller.controller_node import main
try:
    main()
finally:
    trace.close()
