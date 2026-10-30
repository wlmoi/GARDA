# Mock worker + corrupted wiring frames

**PASS — offline mock/simulation, not physical qualification.**

- Worker: actual packaged host controller, synthetic frontal distances and nonzero nominal/action commands. At <=0.22m require all four mock wheel RPS and all safe-twist axes zero.
- Liquid proxy: actual planner UART RTL, CRC/trailer/truncation/framing corruption, sticky fault, valid baseline and reset recovery.
- Evidence: worker_steps.csv/JSONL, corrupt_frames.jsonl, summary.json, liquid_rtl/uart_checkpoints.csv, uart.vcd and simulation.log.
- No water is used. No serial/JTAG/MCU opened; no motor command reaches hardware. Command-zero is not measured stopping distance, inertia, traction, or a person-recognition test. The two scenarios exercise separate host/planner components, not one end-to-end physical chip.
