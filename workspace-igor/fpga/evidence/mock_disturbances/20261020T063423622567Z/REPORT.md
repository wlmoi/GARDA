# Mock worker + corrupted wiring frames

**FAIL — Physical FPGA inference/UART plus host and RTL tests; no physical motors or liquid.**

- Worker: actual packaged host controller, synthetic frontal distances and nonzero nominal/action commands. At <=0.22m require all four mock wheel RPS and all safe-twist axes zero.
- Liquid proxy: actual planner UART RTL, CRC/trailer/truncation/framing corruption, sticky fault, valid baseline and reset recovery.
- Evidence: worker_steps.csv/JSONL, corrupt_frames.jsonl, summary.json, liquid_rtl/uart_checkpoints.csv, uart.vcd and simulation.log.
- No water or physical motor commands. Physical FPGA is required only with --hardware; physical UART rejection results are in physical_corrupt_frames.log. Planner fault-code checks remain RTL simulation, separate from the Parallel8 neural UART protocol. Command-zero does not measure physical stopping distance.
