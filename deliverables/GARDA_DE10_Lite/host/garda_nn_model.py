"""Bit-exact Python model of rtl/garda_core/garda_neural_core.v (24 -> 64 -> 64 -> 4, Q8.8).

Mirrors garda_neural_datapath exactly:
  * ROM layout: W1 at 0 (neuron*24+k), b1 at 1536, W2 at 1600 (neuron*64+k), b2 at 5696,
    W3 at 5760 (neuron*64+k), b3 at 6016; 16-bit two's complement words.
  * accumulator (40 bit) starts at bias << 8, adds operand*weight (signed 16x16).
  * scaled = accumulator >> 8 (arithmetic floor).
  * hidden layers: ReLU, saturate at 32767 (the RTL also raises `fault` then);
    output layer: hard clip to [-256, +256].
Used only for the Control Center's SOFTWARE SIMULATION mode, and checked against the
400 golden outputs before use (verify()).
"""
from __future__ import annotations

from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "assets/neural_24_64_64_4"


def _s16(v: int) -> int:
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


class NeuralModel:
    def __init__(self, rom_path: Path = ASSETS / "bram_unified_weights_padded.mem"):
        words = [int(x, 16) for line in rom_path.read_text().splitlines() for x in line.split("//")[0].split()]
        self.rom = [_s16(w) for w in words]

    def _layer(self, x, n_in, n_out, base, bias_base, output_layer):
        out, fault = [], False
        for n in range(n_out):
            acc = self.rom[bias_base + n] << 8
            for k in range(n_in):
                acc += x[k] * self.rom[base + n * n_in + k]
            scaled = acc >> 8                      # floor, like accumulator[39:8]
            if output_layer:
                out.append(256 if scaled > 256 else (-256 if scaled < -256 else scaled))
            else:
                if scaled > 32767:
                    fault = True
                out.append(0 if scaled < 0 else min(scaled, 32767))
        return out, fault

    def infer(self, inputs_q88: list[int]) -> tuple[list[int], bool]:
        """inputs: 24 signed Q8.8 ints. Returns (4 signed Q8.8 outputs, fault)."""
        x = [_s16(v) for v in inputs_q88]
        h1, f1 = self._layer(x, 24, 64, 0, 1536, False)
        h2, f2 = self._layer(h1, 64, 64, 1600, 5696, False)
        y, _ = self._layer(h2, 64, 4, 5760, 6016, True)
        return y, f1 or f2


def gate(value_q88: int, permit: bool) -> int:
    """Same clamp/gate as the RTL neural command gate (opcode 0x2D)."""
    if not permit:
        return 0
    return 253 if value_q88 > 253 else (-256 if value_q88 < -256 else value_q88)


def verify() -> tuple[int, int]:
    """Compare against the 100 golden vectors; returns (matching outputs, total)."""
    m = NeuralModel()
    ins = [int(x, 16) for x in (ASSETS / "test_inputs.mem").read_text().split()]
    gold = [_s16(int(x, 16)) for x in (ASSETS / "test_outputs.mem").read_text().split()]
    ok = 0
    for n in range(100):
        y, _ = m.infer(ins[n * 24:n * 24 + 24])
        ok += sum(int(a == b) for a, b in zip(y, gold[n * 4:n * 4 + 4]))
    return ok, 400


if __name__ == "__main__":
    print("bit-exact outputs: %d / %d" % verify())
