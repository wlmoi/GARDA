# Parameter evidence screenshots

**For the requested native Quartus GUI proof, use [quartus_gui/README.md](../quartus_gui/README.md).** That folder contains 18 original Computer Use captures. The images in this folder remain browser report-reader visualizations.

These PNGs are genuine Edge headless captures of local report-reader pages. They are **not screenshots of the native Quartus GUI**. The Windows Computer Use runtime failed with `failed to write kernel assets: The system cannot find the path specified`, including after reset. No values were edited in the original tool reports.

Each HTML retains original source paths, hashes and line numbers. Reformatted extracted columns and calculated values are labelled. No Quartus build or simulation was rerun for these captures.

- [01_fitted_resources.png](01_fitted_resources.png) — editable/readable source view: [01_fitted_resources.html](01_fitted_resources.html).
- [02_core_uart_hierarchy.png](02_core_uart_hierarchy.png) — editable/readable source view: [02_core_uart_hierarchy.html](02_core_uart_hierarchy.html).
- [03_memory_packing.png](03_memory_packing.png) — editable/readable source view: [03_memory_packing.html](03_memory_packing.html).
- [04_timing_clock_fmax.png](04_timing_clock_fmax.png) — editable/readable source view: [04_timing_clock_fmax.html](04_timing_clock_fmax.html).
- [05_power.png](05_power.png) — editable/readable source view: [05_power.html](05_power.html).
- [06_latency_acceptance.png](06_latency_acceptance.png) — editable/readable source view: [06_latency_acceptance.html](06_latency_acceptance.html).
- [07_asic_area_raw.png](07_asic_area_raw.png) — editable/readable source view: [07_asic_area_raw.html](07_asic_area_raw.html).
- [08_calculations.png](08_calculations.png) — editable/readable source view: [08_calculations.html](08_calculations.html).
- [09_pinplan.png](09_pinplan.png) — editable/readable source view: [09_pinplan.html](09_pinplan.html).
- [10_programming.png](10_programming.png) — editable/readable source view: [10_programming.html](10_programming.html).

The supplied older PDF screenshot uses a different top/profile and resource totals. It does not establish current Parallel8 values. Core-only resources are hierarchical attribution from the same full fitted build. ASIC metrics establish the protocol-engine layout area; they do not verify a neural ASIC area. See ../../docs/AREA_CORE_UART_ASIC.md for derivations.

All PNG/HTML/source hashes and source-line coverage: screenshots_manifest.json. The ZIP includes PNGs, HTML, this index and manifest; raw reports remain at their referenced repository paths.
