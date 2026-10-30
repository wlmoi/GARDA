# Verification procedure and coverage acceptance

This guide separates measured pass rates, functional bins and structural RTL
coverage. A test definition, screenshot or assertion count alone is not a
coverage percentage. Production RTL is not edited by coverage scripts.

## Measurement policy

Formula: coverage = covered bins / emitted eligible bins x 100. Publish both
counts and percent, by module and metric. Report raw/unwaived results first.
If waivers are introduced, list each source line, reason, reviewer and proof;
publish adjusted and raw results separately. No waivers are currently applied.

UCIS 1.0 standardizes coverage-data interoperability; it does not prescribe a
universal passing percentage. ISO/IEC 27090 addresses AI security threats;
it is not a code-coverage threshold standard.

Project review targets (engineering acceptance policy, not ISO certification):

| Metric | Target | Review rule |
| --- | ---: | --- |
| Mandatory requirement/scenario bins | 100% | Every safety-relevant requirement needs a passing linked test. |
| Executed tests/assertions | 100% pass | Zero failed/error tests; a PASS without expected test count is insufficient. |
| RTL line/block | >=95% raw | Every uncovered safety/recovery path reviewed; no automatic whole-design sign-off. |
| Branch/decision | >=95% raw | True and false outcomes assessed; all safety decision outcomes required. |
| Expression/condition | >=90% raw | Report separately; not interchangeable with branch coverage or MC/DC. |
| FSM legal state/arc | 100% | Denominator must list legal arcs; test invalid-state recovery separately. |
| Toggle | >=90% raw | Review constant bits, counters, ROM/data arrays, unreachable encodings and reset effects. |
| Gate-level tests | 100% of planned tests | Reduced suite allowed with explicit scope; does not substitute for structural coverage. |

Missing measurement means NOT MEASURED; it cannot pass a numerical threshold.
A failed threshold remains visible. Coverage closure never means editing out
needed fault paths, relaxing assertions, or adding arbitrary data to a report.

References:
- https://www.accellera.org/downloads/standards/ucis
- https://verilator.org/guide/latest/simulating.html
- https://verilator.org/guide/latest/exe_verilator_coverage.html
- https://www.iso.org/standard/27090

## Prerequisites and execution order

Run commands below from repository root. Icarus fallback is
`C:/iverilog/bin/{iverilog,vvp}.exe`; Quartus is under
`D:/Quartus-Program/quartus/bin64`. Python fixtures use the repository runtime
where configured. WSL coverage additionally needs Verilator, make and C++.
No command below programs hardware unless explicitly marked hardware.

1. Canonical model export check and baseline policy regression:
   `python fpga/verification/src_policy/run.py --check`
2. Actual baseline DE10 wrapper: `python fpga/verification/run_board_wrapper.py`
3. Optimized candidate: `python fpga/experiments/parallel8/run.py`
4. Planner safety: `python fpga/verification/run_safety_regression.py`
5. Host fixtures: `python fpga/verification/run_host_regression.py`
6. LiDAR fixtures: `python fpga/verification/run_lidar_regression.py`
7. Instrumented coverage, separately for each suite:
   `python tools/run_rtl_coverage.py --suite core`
   (repeat with `uart`, `board`, `gate`).
8. Index all Python test definitions and named RTL checkpoints, then collect
   measured percentages: `python tools/build_verification_inventory.py`.

Additional explicit functional models:
- `python tools/measure_core_fsm.py`: inspect the source-bound existing Icarus
  waveform. Eight legal states and ten normal non-self-loop arcs are the
  declared model. Missing waveform intervals are not interpolated. Reset,
  abort, invalid encodings and self-loops are not silently included as normal
  arcs; illegal-state recovery is a separate supplemental assertion test.
- `python tools/measure_gate_decisions.py`: read the oracle-checked vector
  stream and count true/false outcomes for each of eleven priority decisions
  only when that decision is reached. Denominator is 22 modeled outcomes.
  This is a reviewed functional model, not native expression or MC/DC coverage.

## What each verification suite does

| Suite / command | Stimulus and independent check | Output / how to use |
| --- | --- | --- |
| Source policy `verification/src_policy/run.py --check` | Check model/MEM provenance; generate legal/boundary vectors; integer reference against RTL; activation saturation and rounding; parser/fault tests. | `verification/src_policy/artifacts/`: results, reference hex, logs and waveforms. `--check` prevents accepting silently changed weight exports. This is baseline serial core, not Parallel8 timing. |
| Parallel8 `experiments/parallel8/run.py` | Same canonical golden data; 236 network vectors and activation tests. Inspect hidden activations and final outputs, core protocol faults, abort and reset recovery. UART tests transmit real serialized bits with independent response decoder; board bench uses 50 MHz and 54 clock ticks/bit. | `experiments/parallel8/artifacts/{core,uart,board}.log`, results JSON, VCD/checkpoints. Require all three PASS and no source drift. Do not use baseline core cycles as optimized latency. |
| Baseline wrapper `verification/run_board_wrapper.py` | Actual board wrapper, two-stage reset release, KEY inhibit/latch, serialized request/response and golden output. | `evidence/current_board_wrapper/`; inspect simulation log and named checkpoints. Establishes RTL behavior, not voltage/pin operation on a board. |
| Safety gate `verification/run_safety_regression.py` | Independent Python oracle. Enumerates 1,024 control combinations, velocity domains and angular slew boundaries, plus deterministic random inputs. Compares fault priority and zero/motor-enable outputs. | `evidence/current_safety/gate_vectors.hex`, gate log and checkpoints; 111,210 oracle comparisons in the current suite. Twelve outcomes must all occur. |
| Safety units, same runner | Directed unit boundary cases for configuration, map management, candidate selection, arithmetic and status/fault behavior. | `units.log`, VCD and checkpoint CSV: 31 named checkpoints. Read case names to identify exact contract tested. |
| Safety top, same runner | Integration stimulus through planner control; E-stop, deadline, map freshness/version, result lease and recovery. | `top.log`: 29 checkpoints. This planner top is not proof of neural residual-to-motor integration. |
| Safety UART, same runner | Serial transport and fault handling of legacy planner protocol; header/payload/CRC, timeout/reset and safety behavior. | `uart.log`: 39 checkpoints. Do not feed this protocol to the source-policy bitstream. |
| Host `verification/run_host_regression.py` | Software fixtures exercise real bridge/controller functions: malformed responses, CRC, input domain/NaN, late replies, disconnect/fault latch; command/sensor staleness and stopping behavior. | `evidence/current_host/results.json`. 29 tests currently pass. Serial/ROS fixtures do not measure a physical motor stop. |
| LiDAR `verification/run_lidar_regression.py` | Production parser with fragmented/corrupt data, missing/repeated bins, timestamps, scan completeness/freshness and stream errors. | `evidence/current_lidar/results.json`. 16 tests currently pass. Real hardware/analog performance excluded. |
| Cocotb legacy `verification/run.py gate`, `neural`, `top`, `uart`, `tt` | Directed/random functional checks through separate legacy module or wrapper. Use the selected top and protocol explicitly. `all` selects the default five suites. | `evidence/cocotb_*.xml` and functional JSON. Inspect testcases/failures, not just console return. `tt_generic` uses an archived generic netlist and does not establish current ASIC equivalence. `tt_sram` is explicitly archived/unavailable in this runner. |
| ASIC protocol-engine tests under root `test/` | Separate design's pin/register/program/SRAM/ownership behavior; inspect its Makefile and test-specific dependencies. | Inventory gives exact test function and source line. Do not claim these ran from a Parallel8 suite. |
| Supplied GLS XML | Read-only imported single-test result, waveform and metadata. | `evidence/asic_import/gatelevel_test_results/`: one testcase PASS. No local rerun or complete SDF/netlist provenance established. |
| Quartus build `experiments/parallel8/run.py --build` | RTL synthesis, fitting and constrained STA after candidate regressions. | Fitter/STA/pin reports and SOF. Does not run GLS or code coverage. Power confidence must remain visible. |
| Hardware tests | Require connected fixture, explicit pin/serial selection and physical observations. | No simulation suite implies board programming, measured power or successful motor operation. Do not run robot movement as part of a coverage audit. |

## Structural coverage implementation

`tools/run_rtl_coverage.py` builds the existing SV benches with `--timing`,
`--coverage` and `--assert`, then writes native `coverage.dat`. A copied bench
uses absolute golden-vector paths and no-op waveform statements; stimulus and
assertions remain intact. Raw RTL and copied/original benches are hashed.
The core coverage copy additionally includes
`verification/src_policy/coverage_illegal_state.svh`: inject state 15, require
fault code 6 and zero/invalid result, reset, then require a successful golden
inference at 6916 cycles. Two assertion checks supplement the original 54399,
giving 54401 in this run. The gate copy uses scan temporaries followed by
explicit assignments to DUT inputs for compiled-simulator scheduling;
the 111210 input vectors and expected outputs are unchanged.
Only DUT source-file counters are included; testbench counters are excluded.
No bins are silently waived or promoted to covered. A simulator-specific
failure is reported instead of converted into a passing coverage score.

Read `evidence/rtl_coverage/<suite>/receipt.json`, `build.log`,
`simulation.log` and `coverage.dat`. Counts use hit > 0. Native metric names
are preserved: a Verilator block/line percentage is not textual statement
coverage or MC/DC. Toggle includes reset/initialization activity as emitted
by the tool; it is not necessarily useful-work-only toggling. Expression,
FSM and branch availability depends on the actual installed tool output.
Absent categories are not inferred from functional outcome bins.

Generated `test_inventory.csv` lists every discovered Python `test_*`
definition and named SV checkpoint with source line and readable description.
It is a navigation aid; definitions are not executed results. Use receipts to
bind a test to a run, source hash, simulator, seed and assertion/oracle.

## Reviewing a gap

For each uncovered counter, retain module/file/line, metric, hit count,
scenario needed and resolution. Classify it as missing stimulus, unreachable
legal encoding, constant elaboration, unused/debug signal, or actual defect.
Use directed stimulus or fault injection where meaningful. A waiver requires
reasoned evidence and separate review. Do not use a whole-project average to
hide poor coverage in the UART, reset or safety gate.

For stronger GLS evidence, run the same reference vectors on a hash-bound
netlist using correct cell/macro libraries. Keep functional GLS separate from
SDF-annotated timing GLS; publish annotation success and any unannotated paths.
Reduced gate-level coverage is acceptable as a scoped milestone, with missing
scenarios stated. Existing ASIC timing/overlap violations remain sign-off gaps.

## Defensible presentation wording

“The Parallel8 RTL was verified using an independent integer oracle,
intermediate-activation checks, directed UART fault injection, board-wrapper
simulation and reproducible source-bound regression. Instrumented code
coverage is reported by metric and module, with remaining gaps disclosed.”

Use “rigorously verified within the stated RTL simulation scope” only together
with the exact results and open gaps. Do not imply complete functional proof,
physical sign-off, hardware validation, or ISO certification.

## Ringkasan penggunaan dalam presentasi

Persentase wajib menyertakan pembilang, penyebut, top/module dan jenis
pengukuran. “100% pass rate” berarti seluruh tes yang dijalankan lulus;
ini berbeda dari “100% line coverage”. “100% FSM” di laporan observasi berarti
8/8 state dan 10/10 transisi normal pada model yang disebutkan, bukan semua
urutan input, semua fault, atau ekstraksi FSM native simulator.

Kriteria 95%/90% di atas adalah kebijakan review proyek. Tidak ada klaim
bahwa ISO/IEC 27090 mewajibkan angka tersebut. Untuk metrik yang belum tersedia
gunakan “belum diukur”, jangan mengisinya dengan angka perkiraan. Semua gap
toggle tetap ada pada `uncovered.json`; konstan yang memang tidak mungkin
toggle memerlukan penjelasan, bukan stimulus yang merusak fungsi.
