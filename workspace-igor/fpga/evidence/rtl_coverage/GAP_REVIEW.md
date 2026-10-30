# Coverage gap review

Raw coverage includes every emitted DUT counter; no exclusions or waivers.
Native reports and per-suite percentages are in COVERAGE_RESULTS.md. These
results do not automatically establish ASIC physical sign-off or ISO compliance.

## Core

The original suite missed the illegal-state default case at source line 574.
An explicit injected state 15 now verifies fail-closed error 6, zero/invalid
result and post-reset successful inference. Line coverage rose from 67/68 to
68/68, not by deleting or excluding the default path.

Remaining core toggle misses are listed individually in core/uncovered.json.
Examples are upper bits of the latency counter (legal fixed latency 6916),
unused high error-code bits and bits of constant address/base encodings.
Some signals are mathematically constant under legal operation; those cannot
be honestly driven to toggle without leaving that operating contract. No
adjusted 100% toggle figure is claimed. The report keeps them in the denominator.

## Safety gate

Five toggle misses: fault_code[4..7] and abs_dw[7]. Legal codes are 0..11,
so high four fault bits are zero. Signed 7-bit angular inputs range -64..63;
the largest absolute difference is 127, so bit 7 of abs_dw stays zero.
Native line coverage is 13/13. There is no emitted native branch category
for this gate in the installed instrumentation. The separate reviewed
functional decision model covers 22/22 reached true/false outcomes; it must
not be relabeled native branch/expression coverage.

## Board integration versus unit-level tests

The board suite is focused on real divider timing, reset/KEY behavior and
end-to-end success. It does not reproduce every unit-level protocol fault.
Core and UART percentages inside the board-only run can therefore be lower
than their dedicated suites. Publish per-suite values rather than silently
selecting the best or averaging away missing tests.

Wrapper debug counters/signals have wide upper bits and receive few board-level
transactions. Their low toggle percentage is a real raw gap. It does not
mean the same percentage of requirements failed, and it is not grounds to
claim whole-board coverage closure. Additional representative fault/traffic
tests and separately reviewed constant-bit exclusions are future work.

## Remaining unmeasured or out-of-scope items

Dedicated UART suite: source-policy transport has line 46/47 (97.87%),
branch 46/46 (100%) and toggle 371/517 (71.76%). RX has line 9/10 (90%),
branch 14/14 (100%) and toggle 31/44 (70.45%); TX line and branch are 100%,
toggle 30/43 (69.77%). UART/RX uncovered default-state recovery and remaining
toggle bins are visible in uart/uncovered.json. All 184 functional transactions
and 268 assertions pass, but raw transport toggle/RX line targets are not met.
The board and UART parameterizations have different exercised timing/data
domains; results are not silently merged. Additional invalid-state injection
and representative activity tests remain work for transport coverage closure.

- Native expression/condition and MC/DC coverage.
- Native FSM extraction with complete legal/reset/abort arc analysis. The
  existing explicit waveform model reports eight states and ten normal arcs.
- Full system, ASIC protocol-engine and synthesized-netlist structural coverage.
- SDF-annotated GLS with exact source/netlist/GDS equivalence evidence.
- Physical UART/board testing, metastability/analog effects, adversarial ML,
  authenticated updates and ISO clause-by-clause compliance assessment.

Project line/branch/toggle thresholds are engineering review targets in
VERIFICATION_GUIDE.md. Passing some module thresholds is not whole-design sign-off.
