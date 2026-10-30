# GARDA fixed-model MAC activity

The active 24 → 64 → 64 → 4 core keeps its complete model and arithmetic.
The 6,020 immutable coefficients range from −1,205 to 640, so each MAC
coefficient fits exactly in a signed 12-bit register. Activations remain
signed 16-bit and accumulation remains signed 40-bit. Model generation
fails if a future coefficient would exceed the 12-bit range.

Both registered multiplier inputs become zero whenever either factor is
zero. This isolates changing coefficients during zero ReLU activations.
The existing read enables and inference schedule remain intact.

Reproduce the comparison against the committed pre-optimization core:

```sh
python scripts/measure_neural_logic_activity.py --baseline-ref 275763f
```

The command checks all 6,020 model readbacks and all 400 independently
calculated outputs on each revision. It also checks hidden overflow,
fail-closed host ownership and zero-factor isolation, then writes
[`evidence/neural_logic_activity.json`](../../evidence/neural_logic_activity.json).
Temporary baseline sources and simulation logs stay under the ignored
`verification/build/neural_logic_activity` directory.

Latency remains **3,080 core clocks**, or **61.6 µs at a 50 MHz reference**.
The reference frequency is a conversion, not a post-route timing result.
The comparison counts registered MAC input signal transitions, normalized
to signed 16-bit signals for both revisions. Those counters indicate activity
on this workload; they do not measure power in watts. A fresh placed-and-routed
netlist, timing analysis and technology-specific power analysis are required
before making physical power or signoff claims. No global latency or power
minimum is claimed.
