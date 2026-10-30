# To-Do List for FPGA-Jetson Integration and Demo

## High-Priority Tasks (Critical for Demo)
1. **Correct UART Baud Rate Mismatch**
   - Ensure `fpga_baudrate` parameter is declared and set to `921600` in `bringup.launch.py`.
   - Update `controller_node.py` to use this parameter when instantiating `FPGABridge`.
2. **Wire FPGA UART to Jetson**
   - Verify physical connections: TX/RX pins from DE10‑Nano to Jetson UART header.
   - Confirm voltage level shifting (3.3 V) and ground continuity.
3. **Validate FPGA Bitstream**
   - Build and load the latest `igor_src_policy.sof` bitstream.
   - Run `fpga/scripts/freeze_release.py` to update manifest hashes.
4. **Synchronize Codebases**
   - Mirror changes from `ros2_ws/src/` to `fpga/software_integration/src/`.
   - Run CI verification (`run_host_regression.py`) to ensure no drift.
5. **Implement Demo Waypoint Sequence**
   - Add a simple rectangle waypoint planner (5 m × 3 m) in `global_planner`.
   - Ensure the planner publishes a `Path` that the controller consumes.

## Medium-Priority Tasks (Stability & Clean‑up)
- Register controller alias `cl_drl_dwa_shield`.
- Enable LiDAR obstacle extraction for CBF safety filter.
- Standardize IMU normalization (use 9.81 m/s² for accel Z, rad/s for gyro).
- Replace independent wheel clipping with proportional desaturation.
- Automate weight export to `policy_weights.mem` after retraining.

## Low-Priority Tasks (Documentation & Misc)
- Update `global_planner_docs.md` with demo instructions.
- Add compile/run instructions for Jetson Orin Nano and DE10‑Nano.
- Clean broken links and metadata in repository.
- Provide wiring diagrams and pin mappings in `fpga/docs/CONNECTOR.md`.

*All tasks should be completed before the live demonstration. Prioritize items marked **High-Priority**.*