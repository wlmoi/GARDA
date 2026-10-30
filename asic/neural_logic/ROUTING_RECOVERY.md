# GARDA physical routing recovery

[Physical run 41050845336](https://github.com/wlmoi/GARDA/actions/runs/41050845336)
at commit `275763f33c918603a4e6f560a5ea5d522423505d` failed in
`OpenROAD.RepairDesignPostGRT`, before detailed routing or signoff.
The flow used LibreLane `3.1.0.dev3` and `ihp-sg13cmos5l`.

The job log shows a concrete regression within that run:

| Checkpoint | Global-route overflow | Routed nets | Wirelength |
| --- | ---: | ---: | ---: |
| Before post-route design repair | 0 | 28,817 | 3,375,842 µm |
| After post-route design repair | 529 | 42,251 | 3,944,232 µm |

The repair command imposed a 150 µm wire-length cap. OpenROAD warned
`RSZ-0065` that a limit below 4,286 µm increases wire delay. Repair then
inserted 13,434 buffers on 3,990 nets, increasing area by 26.5%. The
subsequent route stopped with `GRT-0116` congestion.

`src/config.json` now restores `GRT_DESIGN_REPAIR_MAX_WIRE_LENGTH` to its
documented default, **0**, removing the forced 150 µm subdivision. The
post-route repair stage, slew and capacitance margins, rerouting, timing
repair, congestion checks, DRC and LVS checks remain enabled. This changes
a buffering heuristic; it does not waive physical acceptance.
[LibreLane configuration reference](https://librelane.readthedocs.io/en/latest/reference/step_config_vars.html),
[OpenROAD resizer source](https://github.com/The-OpenROAD-Project/OpenROAD/blob/master/src/rsz/src/Resizer.tcl).

The before/after routing figures above describe the failed run, **not a
successful rerun of the corrected configuration**. A fresh full flow must
still complete detailed routing, DRC, LVS, extracted timing, gate-level
tests and TinyTapeout precheck. This IHP diagnosis provides no SKY130
signoff result. Machine-readable provenance is in
[`evidence/neural_logic_routing_diagnosis.json`](../../evidence/neural_logic_routing_diagnosis.json).
