# GARDA FPGA Test Dashboard

Double-click **GARDA - FPGA Test Dashboard** on Desktop, or `fpga/bitstreams/OPEN_MOCK_DASHBOARD.bat`. A local Python server opens the dashboard in your browser. Keep its terminal open. No new packages are needed beyond the existing numpy/pyserial installation.

The buttons invoke the same Python entry points and hardware flags used by the test BAT launchers. They avoid BAT `pause` so the browser can collect the result. Cargo and worker/liquid require real FPGA UART. Numeric tests run 256 vectors plus four invalid/recovery cases. The separate JTAG button explicitly programs the observer image, matching TEST_MOCK_INFERENCE_COM12.bat; other buttons do not program the board. Use the JTAG button only when you want that image loaded.

The dashboard displays detected serial ports, streamed stdout/stderr, exit status, historical summaries and raw CSV/JSONL/log files. Evidence includes synthetic inputs, actual FPGA outputs and independent oracle comparisons. The numeric suite additionally logs TX/RX frame bytes. The cargo test injects maximum positive action AFTER physical inference to exercise the host cargo limit; the injected action is not the FPGA prediction. Worker uses actual board action. Physical motors are never commanded. Planner fault-code tests remain RTL simulation; physical Parallel8 UART rejection is separately logged.

One dashboard job owns the test slot at a time, preventing two dashboard jobs from opening UART concurrently. External terminals can still lock Windows COM ports: close MobaXterm, standalone loggers or test windows first. The hardware adapter retries connection briefly and reports a useful error instead of silently switching to mock. No administrator mode or process termination is used to bypass a port lock.

Historical sessions without a summary appear as INCOMPLETE. PASS follows script exit status; individual summaries and source scopes are available for inspection. Hardware detection alone is never PASS. Logs are saved under `fpga/evidence/dashboard/<UTC>/terminal.log` plus each script's original evidence folder.

The server binds only to 127.0.0.1 on an available port, accepts fixed test identifiers (no arbitrary commands), requires a per-session token for starting tests, and restricts file reads to supported text evidence files under fpga/evidence. A 240-second timeout stops a hung parent job. Avoid closing the server during a running test; wait for completion before closing its terminal.
