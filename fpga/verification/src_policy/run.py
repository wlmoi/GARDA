#!/usr/bin/env python3
"""Reproducible source-policy export + independent integer/RTL regression (stdlib)."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORKSPACE = ROOT.parent
SOURCE = WORKSPACE / "src/igor_navigation/igor_navigation/weights"
RTL = ROOT / "rtl/igor_src_policy"
ARTIFACTS = HERE / "artifacts"
SHAPES = {"w1": (128, 74), "b1": (128,), "w2": (64, 128), "b2": (64,),
          "w3": (3, 64), "b3": (3,)}


def flatten(value):
    return [item for row in value for item in row] if isinstance(value[0], list) else value


def signed16(value):
    return value - 65536 if value & 32768 else value


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export(check):
    source_json = SOURCE / "model_weights.json"
    model = json.loads(source_json.read_text(encoding="utf-8"))
    quantized = {}
    hashes = {str(source_json.relative_to(WORKSPACE)): sha(source_json)}
    for name, shape in SHAPES.items():
        values = model[name]
        actual = (len(values), len(values[0])) if len(shape) == 2 else (len(values),)
        if actual != shape:
            raise ValueError(f"{name}: source shape {actual} != expected {shape}")
        # Source retrain_ai.py uses numpy.round (ties to even). Every JSON number
        # originated as float32; multiplication by power-of-two is exact here.
        q = [min(32767, max(-32768, round(float(x) * 256))) for x in flatten(values)]
        original = SOURCE / f"hardware/layer{name[-1]}_{name[0]}.mem"
        supplied = [signed16(int(x, 16)) for x in original.read_text().split()]
        if supplied != q:
            raise ValueError(f"{original}: does not match JSON Q8.8 export")
        quantized[name] = q
        hashes[str(original.relative_to(WORKSPACE))] = sha(original)
    unified = "".join(f"{value & 65535:04X}\n"
                      for name in SHAPES for value in quantized[name])
    # Explicit zero padding avoids Quartus' 5000-iteration elaboration limit
    # and allows the canonical synchronous ROM to infer M10K directly.
    unified += "0000\n" * (32768 - 18051)
    target = RTL / "policy_weights.mem"
    if check:
        if not target.exists() or target.read_text() != unified:
            raise ValueError("Stale policy_weights.mem: run this script without --check")
    else:
        target.write_text(unified, encoding="ascii")
    hashes[str(target.relative_to(WORKSPACE))] = sha(target)
    manifest = {"architecture": [74, 128, 64, 3], "words": 18051, "storage_words": 32768,
                "layout": {"w1": [0, 9471], "b1": [9472, 9599],
                           "w2": [9600, 17791], "b2": [17792, 17855],
                           "w3": [17856, 18047], "b3": [18048, 18050]},
                "source_metadata": model.get("metadata"), "sha256": hashes}
    (ARTIFACTS / "model_provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return model, quantized, manifest


def integer_layer(inputs, weights, biases, rows, output=False):
    result = []
    saturated = False
    for row in range(rows):
        total = biases[row] * 256
        total += sum(x * w for x, w in zip(inputs, weights[row * len(inputs):(row+1) * len(inputs)]))
        if not -(1 << 39) <= total < (1 << 39):
            raise AssertionError("40-bit accumulator bound exceeded")
        scaled = total // 256
        if output:
            result.append(min(256, max(-256, scaled)))
        else:
            saturated |= scaled > 32767
            result.append(min(32767, max(0, scaled)))
    return result, saturated


def golden(observation, q):
    # Python unbounded integer dot product is intentionally independent of RTL
    # address scheduling, sign extension, registers, and expression sizing.
    h1, s1 = integer_layer(observation, q["w1"], q["b1"], 128)
    h2, s2 = integer_layer(h1, q["w2"], q["b2"], 64)
    out, _ = integer_layer(h2, q["w3"], q["b3"], 3, output=True)
    return h1, h2, out, s1 or s2


def float_reference(observation, model):
    values = [x / 256 for x in observation]
    for layer in range(1, 4):
        values = [sum(a * b for a, b in zip(row, values)) + bias
                  for row, bias in zip(model[f"w{layer}"], model[f"b{layer}"])]
        values = [min(1.0, max(-1.0, x)) if layer == 3 else max(0.0, x) for x in values]
    return values


def write_hex(name, values, width=4):
    mask = (1 << (width * 4)) - 1
    (ARTIFACTS / name).write_text("".join(f"{x & mask:0{width}x}\n" for x in values), encoding="ascii")


def vectors(model, q):
    rng = random.Random(0x1A0A74128)
    tests = [("zeros", [0] * 74), ("clear_front_neutral", [256]*64 + [0]*10),
             ("all_plus_one", [256]*74), ("signed_minus_one", [256]*64 + [-256]*10),
             ("alternating_lsb", [i % 2 for i in range(74)]),
             ("all_int16_max", [32767]*74), ("all_int16_min", [-32768]*74),
             ("alternating_int16_extremes", [32767 if i % 2 else -32768 for i in range(74)])]
    # Walking ±1 LSB validates every input address and signed contribution.
    for i in range(74):
        for polarity in (-1, 1):
            value = [0]*74
            value[i] = polarity
            tests.append((f"walking_{i}_{polarity:+d}", value))
    for n in range(64):
        tests.append((f"normalized_random_{n}",
                      [rng.randint(0, 256) for _ in range(64)] +
                      [rng.randint(-256, 256) for _ in range(10)]))
    for n in range(16):
        tests.append((f"fullrange_random_{n}", [rng.randint(-32768, 32767) for _ in range(74)]))
    observations, hidden1, hidden2, expected, sat = [], [], [], [], []
    details, errors = [], []
    for name, observation in tests:
        h1, h2, out, saturated = golden(observation, q)
        observations.extend(observation); hidden1.extend(h1); hidden2.extend(h2)
        expected.extend(out); sat.append(int(saturated))
        normalized = all(0 <= x <= 256 for x in observation[:64]) and all(-256 <= x <= 256 for x in observation[64:])
        fp = float_reference(observation, model)
        error = max(abs(actual/256 - reference) for actual, reference in zip(out, fp))
        if normalized:
            errors.append(error)
        details.append({"name": name, "q8_8_actions": out, "hidden_saturated": saturated,
                        "normalized_contract": normalized, "fp64_source_reference": fp,
                        "max_abs_quantization_error": error})
    write_hex("observations.hex", observations)
    write_hex("hidden1.hex", hidden1); write_hex("hidden2.hex", hidden2)
    write_hex("expected.hex", expected); write_hex("saturated.hex", sat, 1)
    # Activation sweeps cover floor and all clamp boundaries independently.
    boundaries = [-((1 << 39)), (1 << 39)-1]
    for raw in [-32769, -32768, -257, -256, -255, -1, 0, 1, 255, 256, 257, 32766, 32767, 32768]:
        boundaries.extend(raw*256 + fraction for fraction in [-1, 0, 1, 127, 128, 255])
    boundaries += [rng.randrange(-(1 << 39), 1 << 39) for _ in range(4096)]
    activation_inputs, activation_values = [], []
    for accumulator in boundaries:
        for output_layer in (0, 1):
            floor = accumulator // 256
            result = min(256, max(-256, floor)) if output_layer else min(32767, max(0, floor))
            saturated = int(not output_layer and floor > 32767)
            activation_inputs.append(((accumulator & ((1 << 40)-1)) << 1) | output_layer)
            activation_values.append((saturated << 16) | (result & 65535))
    write_hex("activation_inputs.hex", activation_inputs, 11)
    write_hex("activation_expected.hex", activation_values, 5)
    characterization = {"seed": "0x1A0A74128", "vector_count": len(tests),
                        "activation_cases": len(activation_inputs),
                        "normalized_vector_count": len(errors),
                        "normalized_max_abs_error": max(errors),
                        "normalized_mean_max_abs_error": sum(errors)/len(errors),
                        "numerical_claim": "RTL equals the specified integer model; FP32 equivalence is not claimed.",
                        "fp_reference_precision": "Python double on source FP32 coefficients; not ONNX execution.",
                        "tests": details}
    (ARTIFACTS / "vectors.json").write_text(json.dumps(characterization, indent=2) + "\n")
    return len(tests), len(activation_inputs), characterization


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify checked-in exported ROM without changing it")
    parser.add_argument("--export-only", action="store_true")
    args = parser.parse_args()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    model, q, manifest = export(args.check)
    count, activation_count, characterization = vectors(model, q)
    if args.export_only:
        print(f"Export verified: 18051 source words, {count} vectors, {activation_count} activation checks")
        return
    simulator = shutil.which("iverilog") or ("C:/iverilog/bin/iverilog.exe" if Path("C:/iverilog/bin/iverilog.exe").exists() else None)
    runtime = shutil.which("vvp") or ("C:/iverilog/bin/vvp.exe" if Path("C:/iverilog/bin/vvp.exe").exists() else None)
    if not simulator or not runtime:
        raise SystemExit("Icarus Verilog (iverilog and vvp) is required on PATH")
    results = {}
    rtl_hashes = {}
    for suite in ("core", "uart"):
        suite_started = time.monotonic()
        output = ARTIFACTS / f"{suite}.vvp"
        sources = [RTL / "igor_src_policy_rom.v", RTL / "igor_src_policy_core.v"]
        if suite == "uart":
            sources += [ROOT / "rtl/igor_uart_rx.v", ROOT / "rtl/igor_uart_tx.v", RTL / "igor_src_policy_uart.v"]
        sources.append(HERE / f"tb_src_policy_{suite}.sv")
        before_hashes = {str(path.relative_to(ROOT)): sha(path) for path in sources}
        command = [simulator, "-g2012", "-Wall", "-s", f"tb_src_policy_{suite}",
                   f"-DVECTOR_COUNT={count}", f"-DACTIVATION_COUNT={activation_count}",
                   "-o", str(output)] + [str(x) for x in sources]
        build = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        (ARTIFACTS / f"{suite}_compile.log").write_text(build.stdout + build.stderr)
        if build.returncode:
            raise RuntimeError(build.stdout + build.stderr)
        execution = subprocess.run([runtime, str(output)], cwd=ROOT, capture_output=True, text=True, timeout=900)
        log = execution.stdout + execution.stderr
        (ARTIFACTS / f"{suite}.log").write_text(log)
        if execution.returncode or f"PASS {suite}" not in log:
            raise RuntimeError(log)
        if any(sha(path) != before_hashes[str(path.relative_to(ROOT))] for path in sources):
            raise RuntimeError(f"{suite}: RTL/testbench changed during simulation; rerun verification")
        rtl_hashes.update(before_hashes)
        print(log.strip())
        results[suite] = {"passed": True, "log": f"{suite}.log", "waveform": f"{suite}.vcd",
                          "assertions": int(re.search(r"(\d+) assertions", log).group(1)),
                          "elapsed_seconds": round(time.monotonic()-suite_started, 3)}
        if suite == "uart":
            results[suite]["directed_transactions"] = int(re.search(r"(\d+) directed transactions", log).group(1))
    model_hash = manifest["sha256"][str((RTL / "policy_weights.mem").relative_to(WORKSPACE))]
    if sha(RTL / "policy_weights.mem") != model_hash:
        raise RuntimeError("ROM changed during verification; rerun the complete regression")
    results.update({"model_words": 18051, "storage_words": 32768, "model_sha256": model_hash,
                    "rtl_and_testbench_sha256": rtl_hashes,
                    "core_vectors": count, "activation_cases": activation_count,
                    "latency_cycles": 54348, "latency_ms_at_50mhz": 54348/50000,
                    "normalized_max_abs_error": characterization["normalized_max_abs_error"],
                    "board_measurement": False,
                    "claim": "Simulation equivalence to specified quantized source model; no formal all-input proof or physical FPGA measurement.",
                    "elapsed_seconds": round(time.monotonic()-started, 3)})
    (ARTIFACTS / "results.json").write_text(json.dumps(results, indent=2)+"\n")
    print("PASS source-policy regression; artifacts:", ARTIFACTS)


if __name__ == "__main__":
    main()
