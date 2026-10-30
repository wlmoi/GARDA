# Mock AI surge cargo: hard forward cap

Double-click **GARDA - Mock AI Surge Cargo** on Desktop. It runs `fpga/scripts/mock_ai_surge_cargo.py` automatically and keeps the terminal open.

The script enables the actual packaged controller's `cargo_mode=True`. This mode limits forward output to **0.15 m/s at every distance**, including 1.20 m, 1.50 m and clear space at 3.50 m. The distance envelope may reduce speed further; at or below 0.22 m all motion commands are zero. Zero nominal command also remains zero.

For ROS deployment, enable `--ros-args -p cargo_mode:=true` on the controller node. Default non-cargo operation remains unchanged. This is a host controller limit before conversion to wheel RPS, not an FPGA RTL speed limiter; existing FPGA serial connections are unchanged.

30 checks exercise both `cl_drl` and `cl_drl_cbf`: 14 distances per mode plus zero-command checks. Synthetic AI action is `[1,0,0]`, nominal forward input is 0.60 m/s. A deliberately excessive mock filter output of 10 m/s checks that the final limit cannot be bypassed by that filter. Expected forward speed and all four wheel RPS are checked independently; every case explicitly asserts output <=0.15 m/s (numerical tolerance 1e-6).

Latest validation: 30/30 cargo mock checks PASS; existing host regression 29/29 PASS. This replaces the earlier distance-only interpretation of the cargo requirement. Old timestamped logs remain historical evidence of that earlier behavior.

Each execution writes timestamped CSV, JSONL and summary/source hashes under `fpga/evidence/mock_ai_surge_cargo/`. No COM port is opened and no physical motion occurs. Actual sensing, FPGA inference and physical motor speed are not measured by this software mock.

## Physical FPGA Desktop mode
The Desktop launcher now passes `--hardware`: actual observations are sent to the FPGA over the detected Prolific UART at 921600 baud, responses must match the independent integer oracle, and each transaction is logged in `physical_fpga_transactions.jsonl`. Maximum positive action is deliberately injected AFTER real inference to stress the host cap; it is not claimed to be the FPGA's own predicted action. Missing board/invalid response prevents hardware PASS. Direct Python invocation without the flag retains offline mode.
