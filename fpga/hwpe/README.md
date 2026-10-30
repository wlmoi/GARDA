# GARDA policy MMIO experiment

This is an original register adapter around the existing `fpga/experiments/parallel16/garda_src_policy_core.v` and its sixteen weight-bank files. It is inspired by the control/streaming separation of the supplied HWPE reference. No dynamic-range audio compressor, PULP modules or third-party RTL are copied into this experiment. The wrapper currently has a simple request/response interface, not a TCDM or a complete PULP HWPE bus, and has no CPU, DMA, memory fabric or actuator safety gate. It is not part of the board design.

A request transfers on a rising edge when `req_valid && req_ready`; a response is held stable until `resp_ready`. One response may be outstanding. `resp_error` marks an invalid register or operation. The caller must hold a blocked request stable. Addresses are byte offsets, accesses are full 32-bit words, and the bus bridge must validate alignment and byte enables.

| Offset | Access | Meaning |
| --- | --- | --- |
| 0x00 | W | command: 1 start, 2 abort, 4 reset; commands are exclusive |
| 0x04 | R | bit 0 busy, 1 done, 2 fault, 3 saturation, bits 7:4 error code |
| 0x08 | R/W | input index, 0–73 |
| 0x0c | W | signed Q8.8 input in low 16 bits; index increments after accepted write |
| 0x10/14/18 | R | signed Q8.8 action, sign extended to 32 bits |
| 0x1c | R | core inference cycles |

Input writes and start are rejected while busy or faulted. Core fault or done asserts `irq` until the core is reset, aborted as applicable, or the next frame starts to load. A start with an incomplete frame is accepted by the adapter and causes a core fault; reset clears it. Results are zero until the core reports a valid completed inference. Software must enforce a timeout and appropriate independent robot safety interlocks.

Run `python fpga/hwpe/run_test.py` with `iverilog` and `vvp` on PATH. This tests response backpressure, invalid accesses, incomplete frames, abort, reset, reset between frames, all 236 independently generated vectors and 708 sign-extended outputs, and the 3,556-cycle Parallel16 inference. It also checks output-response stability while the request address changes, an invalid command, and a rejected start while busy. A successful run writes `mmio-regression.json` with SHA-256 hashes of the test, adapter, core, bank files and vector fixtures; Hashes are computed after normalizing CRLF to LF; compare them before relying on a saved receipt. The simulation is not a timing, synthesis, bitstream, physical-board or SKY130 GDS result. The existing implementation and images remain unchanged.
