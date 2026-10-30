# ASIC diagnostics imported from user archive

Top: **tt_um_igorchip**; PDK: **ihp-sg13cmos5l**; clock constraint **20 ns**.
These are results of the RTL/design used in the supplied run, not a new local build or measured silicon.
No equivalence to the local FPGA Parallel8 model or source commit is inferred.

## Post-route power

| Corner | Internal mW | Switching mW | Dynamic mW | Leakage mW | Total mW |
|---|---:|---:|---:|---:|---:|
| nom_fast_1p32V_m40C | 2.068604 | 0.4088668 | 2.4774708 | 0.1845691 | 2.66204 |
| nom_slow_1p08V_125C | 1.35124 | 0.2528204 | 1.6040604 | 0.01664386 | 1.620704 |
| nom_typ_1p20V_25C | 1.663574 | 0.3237679 | 1.9873419 | 0.0500292 | 2.037372 |

Internal + switching = dynamic. Do not call switching alone total dynamic.
Pad group is reported as zero: this is not proof of zero package/shuttle/board I/O power.
No VCD/SAIF or activity-coverage evidence was established in this archive; no Quartus confidence label is assigned.

## Sign-off observations

- Worst setup: **-2.637271808916401 ns**; TNS **-258.60470763441555 ns**; **253 setup violations**.
- Max slew/cap/fanout violation counts: **26 / 11 / 58**.
- Illegal overlap metric: **42**. Requires rule/waiver review; do not silently treat as zero.
- Source config has `ERROR_ON_ILLEGAL_OVERLAPS=false` and `RUN_MAGIC_DRC=false`. A completed flow is not proof that these checks passed.
- KLayout DRC: 0; routing DRC: 0; LVS errors: 0; antenna count: 0.
- Workflow YAML describes requested jobs; it does not establish their exit status. Precheck and gate-level success need their actual artifacts.
- 50 MHz is the configured target; the negative slow-corner setup slack prevents claiming qualified all-corner 50 MHz.
- Inference-cycle count, algorithm accuracy and physical silicon power are not established by this diagnostics package.

- GDS/OAS, SPEF and SDF are referenced by paths in state JSON but are not included as those file types in this archive. Their paths alone do not provide layout hashes or a reproducible gate-level/timing run.

## Complete numeric records

- [Final metrics CSV](final_metrics.csv): **199** original metrics, source lines, units and SHA.
- [All JSON values](all_json_values.csv): **201365** leaf values from every JSON, including each stage/config; JSON pointers preserve identity.
- [All power reports](all_power_reports.csv): **60** group rows across stages/corners. Do not mix pre-route with post-route.
- [Raw final metrics](raw/runs/wokwi/final/metrics.json) and [post-route timing](raw/runs/wokwi/56-openroad-stapostpnr/summary.rpt).
- [Archive inventory](archive_inventory.csv): member SHA/CRC and preservation location for every file.
- [Original source.zip](source.zip) preserves all bytes, including ODB databases. All non-ODB files are also extracted under `raw/`.
- [Summary JSON](summary.json) retains every final metric without rounding.

## Every final metric

| Metric | Raw value | Unit |
|---|---:|---|
| `design__lint_error__count` | 0 | count |
| `design__lint_timing_construct__count` | 0 | count |
| `design__lint_warning__count` | 20 | count |
| `design__inferred_latch__count` | 0 | count |
| `design__instance__count` | 71108 | count |
| `design__instance__area` | 895165 | um^2 |
| `design__instance_unmapped__count` | 0 | count |
| `synthesis__check_error__count` | 0 | count |
| `design__max_slew_violation__count__corner:nom_fast_1p32V_m40C` | 11 | count |
| `design__max_fanout_violation__count__corner:nom_fast_1p32V_m40C` | 58 | count |
| `design__max_cap_violation__count__corner:nom_fast_1p32V_m40C` | 11 | count |
| `power__internal__total` | 0.0016635743668302894 | W |
| `power__switching__total` | 0.00032376786111854017 | W |
| `power__leakage__total` | 5.002920079277828e-05 | W |
| `power__total` | 0.0020373715087771416 | W |
| `clock__skew__worst_hold__corner:nom_fast_1p32V_m40C` | -0.3596245625304826 | ns |
| `clock__skew__worst_setup__corner:nom_fast_1p32V_m40C` | 0.3362288043153038 | ns |
| `timing__hold__ws__corner:nom_fast_1p32V_m40C` | 0.10757656181461074 | ns |
| `timing__setup__ws__corner:nom_fast_1p32V_m40C` | 4.051679995079492 | ns |
| `timing__hold__tns__corner:nom_fast_1p32V_m40C` | 0 | ns |
| `timing__setup__tns__corner:nom_fast_1p32V_m40C` | 0 | ns |
| `timing__hold__wns__corner:nom_fast_1p32V_m40C` | 0 | ns |
| `timing__setup__wns__corner:nom_fast_1p32V_m40C` | 0 | ns |
| `timing__hold_vio__count__corner:nom_fast_1p32V_m40C` | 0 | count |
| `timing__hold_r2r__ws__corner:nom_fast_1p32V_m40C` | 0.107577 | ns |
| `timing__hold_r2r_vio__count__corner:nom_fast_1p32V_m40C` | 0 | count |
| `timing__setup_vio__count__corner:nom_fast_1p32V_m40C` | 0 | count |
| `timing__setup_r2r__ws__corner:nom_fast_1p32V_m40C` | 4.969062 | ns |
| `timing__setup_r2r_vio__count__corner:nom_fast_1p32V_m40C` | 0 | count |
| `design__max_slew_violation__count__corner:nom_slow_1p08V_125C` | 26 | count |
| `design__max_fanout_violation__count__corner:nom_slow_1p08V_125C` | 58 | count |
| `design__max_cap_violation__count__corner:nom_slow_1p08V_125C` | 11 | count |
| `clock__skew__worst_hold__corner:nom_slow_1p08V_125C` | -0.47193839061399667 | ns |
| `clock__skew__worst_setup__corner:nom_slow_1p08V_125C` | 0.4274973551711248 | ns |
| `timing__hold__ws__corner:nom_slow_1p08V_125C` | 0.6038820725510783 | ns |
| `timing__setup__ws__corner:nom_slow_1p08V_125C` | -2.637271808916401 | ns |
| `timing__hold__tns__corner:nom_slow_1p08V_125C` | 0 | ns |
| `timing__setup__tns__corner:nom_slow_1p08V_125C` | -258.60470763441555 | ns |
| `timing__hold__wns__corner:nom_slow_1p08V_125C` | 0 | ns |
| `timing__setup__wns__corner:nom_slow_1p08V_125C` | -2.637271808916401 | ns |
| `timing__hold_vio__count__corner:nom_slow_1p08V_125C` | 0 | count |
| `timing__hold_r2r__ws__corner:nom_slow_1p08V_125C` | 0.603882 | ns |
| `timing__hold_r2r_vio__count__corner:nom_slow_1p08V_125C` | 0 | count |
| `timing__setup_vio__count__corner:nom_slow_1p08V_125C` | 253 | count |
| `timing__setup_r2r__ws__corner:nom_slow_1p08V_125C` | -2.637272 | ns |
| `timing__setup_r2r_vio__count__corner:nom_slow_1p08V_125C` | 253 | count |
| `design__max_slew_violation__count__corner:nom_typ_1p20V_25C` | 15 | count |
| `design__max_fanout_violation__count__corner:nom_typ_1p20V_25C` | 58 | count |
| `design__max_cap_violation__count__corner:nom_typ_1p20V_25C` | 11 | count |
| `clock__skew__worst_hold__corner:nom_typ_1p20V_25C` | -0.3980021702640299 | ns |
| `clock__skew__worst_setup__corner:nom_typ_1p20V_25C` | 0.3686861753581774 | ns |
| `timing__hold__ws__corner:nom_typ_1p20V_25C` | 0.2854233596926192 | ns |
| `timing__setup__ws__corner:nom_typ_1p20V_25C` | 2.2165239160364947 | ns |
| `timing__hold__tns__corner:nom_typ_1p20V_25C` | 0 | ns |
| `timing__setup__tns__corner:nom_typ_1p20V_25C` | 0 | ns |
| `timing__hold__wns__corner:nom_typ_1p20V_25C` | 0 | ns |
| `timing__setup__wns__corner:nom_typ_1p20V_25C` | 0 | ns |
| `timing__hold_vio__count__corner:nom_typ_1p20V_25C` | 0 | count |
| `timing__hold_r2r__ws__corner:nom_typ_1p20V_25C` | 0.285423 | ns |
| `timing__hold_r2r_vio__count__corner:nom_typ_1p20V_25C` | 0 | count |
| `timing__setup_vio__count__corner:nom_typ_1p20V_25C` | 0 | count |
| `timing__setup_r2r__ws__corner:nom_typ_1p20V_25C` | 2.216524 | ns |
| `timing__setup_r2r_vio__count__corner:nom_typ_1p20V_25C` | 0 | count |
| `design__max_slew_violation__count` | 26 | count |
| `design__max_fanout_violation__count` | 58 | count |
| `design__max_cap_violation__count` | 11 | count |
| `clock__skew__worst_hold` | -0.3596245625304826 | ns |
| `clock__skew__worst_setup` | 0.3362288043153038 | ns |
| `timing__hold__ws` | 0.10757656181461074 | ns |
| `timing__setup__ws` | -2.637271808916401 | ns |
| `timing__hold__tns` | 0 | ns |
| `timing__setup__tns` | -258.60470763441555 | ns |
| `timing__hold__wns` | 0 | ns |
| `timing__setup__wns` | -2.637271808916401 | ns |
| `timing__hold_vio__count` | 0 | count |
| `timing__hold_r2r__ws` | 0.107577 | ns |
| `timing__hold_r2r_vio__count` | 0 | count |
| `timing__setup_vio__count` | 253 | count |
| `timing__setup_r2r__ws` | -2.637272 | ns |
| `timing__setup_r2r_vio__count` | 253 | count |
| `design__die__bbox` | 0.0 0.0 1289.28 710.64 | raw; see source definition |
| `design__core__bbox` | 2.88 3.78 1286.4 706.86 | raw; see source definition |
| `design__io` | 45 | count |
| `design__die__area` | 916214 | um^2 |
| `design__core__area` | 902417 | um^2 |
| `design__instance__count__stdcell` | 5316 | count |
| `design__instance__area__stdcell` | 69830.8 | um^2 |
| `design__instance__count__macros` | 1 | count |
| `design__instance__area__macros` | 28127.1 | um^2 |
| `design__instance__count__padcells` | 0 | count |
| `design__instance__area__padcells` | 0 | um^2 |
| `design__instance__count__cover` | 0 | count |
| `design__instance__area__cover` | 0 | um^2 |
| `design__instance__utilization` | 0.108551 | ratio |
| `design__instance__utilization__stdcell` | 0.0798714 | ratio |
| `design__rows` | 223 | count |
| `design__rows:CoreSite` | 223 | count |
| `design__sites` | 477865 | count |
| `design__sites:CoreSite` | 477865 | count |
| `design__instance__count__class:macro` | 1 | count |
| `design__instance__area__class:macro` | 28127.1 | um^2 |
| `design__instance__count__class:buffer` | 9 | count |
| `design__instance__area__class:buffer` | 65.3184 | um^2 |
| `design__instance__count__class:inverter` | 133 | count |
| `design__instance__area__class:inverter` | 738.461 | um^2 |
| `design__instance__count__class:sequential_cell` | 403 | count |
| `design__instance__area__class:sequential_cell` | 19742.5 | um^2 |
| `design__instance__count__class:multi_input_combinational_cell` | 3504 | count |
| `design__instance__area__class:multi_input_combinational_cell` | 34493.6 | um^2 |
| `flow__warnings__count` | 1 | count |
| `flow__errors__count` | 0 | count |
| `flow__warnings__type_count` | 1 | count |
| `flow__warnings__count:ORD-0039` | 1 | count |
| `flow__warnings__count:PSM-0038` | 56 | count |
| `flow__warnings__count:PSM-0039` | 3 | count |
| `design__power_grid_violation__count__net:VPWR` | 0 | count |
| `design__power_grid_violation__count__net:VGND` | 0 | count |
| `design__power_grid_violation__count` | 0 | count |
| `timing__drv__floating__nets` | 0 | raw; see source definition |
| `timing__drv__floating__pins` | 0 | raw; see source definition |
| `design__instance__displacement__total` | 2115.13 | um |
| `design__instance__displacement__mean` | 0.401 | um |
| `design__instance__displacement__max` | 8.758 | um |
| `route__wirelength__estimated` | 326558 | um |
| `design__violations` | 0 | raw; see source definition |
| `design__instance__count__class:timing_repair_buffer` | 1144 | count |
| `design__instance__area__class:timing_repair_buffer` | 13002 | um^2 |
| `design__instance__count__class:clock_buffer` | 56 | count |
| `design__instance__area__class:clock_buffer` | 1320.88 | um^2 |
| `design__instance__count__class:clock_inverter` | 24 | count |
| `design__instance__area__class:clock_inverter` | 234.058 | um^2 |
| `flow__warnings__count:CTS-0041` | 1 | count |
| `design__instance__count__setup_buffer` | 22 | count |
| `design__instance__count__hold_buffer` | 52 | count |
| `global_route__vias` | 20 | count |
| `global_route__wirelength` | 512208 | um |
| `antenna__violating__nets` | 0 | raw; see source definition |
| `antenna__violating__pins` | 0 | raw; see source definition |
| `route__antenna_violation__count` | 0 | count |
| `antenna_diodes_count` | 6 | count |
| `design__instance__count__class:antenna_cell` | 43 | count |
| `design__instance__area__class:antenna_cell` | 234.058 | um^2 |
| `route__net` | 5280 | count |
| `route__net__special` | 2 | count |
| `route__drc_errors__iter:0` | 76 | raw; see source definition |
| `route__wirelength__iter:0` | 398811 | um |
| `route__drc_errors__iter:1` | 6 | raw; see source definition |
| `route__wirelength__iter:1` | 398763 | um |
| `route__drc_errors__iter:2` | 4 | raw; see source definition |
| `route__wirelength__iter:2` | 398764 | um |
| `route__drc_errors__iter:3` | 0 | raw; see source definition |
| `route__wirelength__iter:3` | 398770 | um |
| `route__drc_errors__iter:4` | 1 | raw; see source definition |
| `route__wirelength__iter:4` | 398798 | um |
| `route__drc_errors__iter:5` | 0 | raw; see source definition |
| `route__wirelength__iter:5` | 398798 | um |
| `route__drc_errors` | 0 | raw; see source definition |
| `route__wirelength` | 398770 | um |
| `route__vias` | 42865 | count |
| `route__vias__singlecut` | 42865 | count |
| `route__vias__multicut` | 0 | count |
| `flow__warnings__count:DRT-0349` | 7 | count |
| `design__disconnected_pin__count` | 5 | count |
| `design__critical_disconnected_pin__count` | 0 | count |
| `route__wirelength__max` | 964.685 | um |
| `design__instance__count__class:fill_cell` | 65791 | count |
| `design__instance__area__class:fill_cell` | 797207 | um^2 |
| `timing__unannotated_net__count__corner:nom_fast_1p32V_m40C` | 33 | count |
| `timing__unannotated_net_filtered__count__corner:nom_fast_1p32V_m40C` | 0 | count |
| `timing__unannotated_net__count__corner:nom_slow_1p08V_125C` | 33 | count |
| `timing__unannotated_net_filtered__count__corner:nom_slow_1p08V_125C` | 0 | count |
| `timing__unannotated_net__count__corner:nom_typ_1p20V_25C` | 33 | count |
| `timing__unannotated_net_filtered__count__corner:nom_typ_1p20V_25C` | 0 | count |
| `timing__unannotated_net__count` | 33 | count |
| `timing__unannotated_net_filtered__count` | 0 | count |
| `design_powergrid__voltage__worst__net:VPWR__corner:nom_typ_1p20V_25C` | 1.19967 | V |
| `design_powergrid__drop__average__net:VPWR__corner:nom_typ_1p20V_25C` | 1.19999 | V |
| `design_powergrid__drop__worst__net:VPWR__corner:nom_typ_1p20V_25C` | 0.000326908 | V |
| `design_powergrid__voltage__worst__net:VGND__corner:nom_typ_1p20V_25C` | 0.000356734 | V |
| `design_powergrid__drop__average__net:VGND__corner:nom_typ_1p20V_25C` | 7.91346e-06 | V |
| `design_powergrid__drop__worst__net:VGND__corner:nom_typ_1p20V_25C` | 0.000356734 | V |
| `design_powergrid__voltage__worst` | 0.000356734 | V |
| `design_powergrid__voltage__worst__net:VPWR` | 1.19967 | V |
| `design_powergrid__drop__worst` | 0.000356734 | V |
| `design_powergrid__drop__worst__net:VPWR` | 0.000326908 | V |
| `design_powergrid__voltage__worst__net:VGND` | 0.000356734 | V |
| `design_powergrid__drop__worst__net:VGND` | 0.000356734 | V |
| `ir__voltage__worst` | 1.2 | V |
| `ir__drop__avg` | 8.5e-06 | V |
| `ir__drop__worst` | 0.000327 | V |
| `klayout__drc_error__count` | 0 | count |
| `magic__illegal_overlap__count` | 42 | count |
| `design__lvs_device_difference__count` | 0 | count |
| `design__lvs_net_difference__count` | 0 | count |
| `design__lvs_property_fail__count` | 0 | count |
| `design__lvs_error__count` | 0 | count |
| `design__lvs_unmatched_device__count` | 0 | count |
| `design__lvs_unmatched_net__count` | 0 | count |
| `design__lvs_unmatched_pin__count` | 0 | count |
