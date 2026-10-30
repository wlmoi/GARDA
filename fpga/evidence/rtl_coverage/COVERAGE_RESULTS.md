# Measured RTL coverage

Raw, unwaived DUT counters; percent = hit / total x 100. Testbench excluded.

| Suite | RTL | Metric | Hit / Total | Percent |
| --- | --- | --- | ---: | ---: |
| board | igor_src_policy_core.v | v_branch | 95 / 96 | 98.96% |
| board | igor_src_policy_core.v | v_line | 60 / 68 | 88.24% |
| board | igor_src_policy_core.v | v_toggle | 789 / 908 | 86.89% |
| board | igor_src_policy_de10_nano.v | v_branch | 6 / 6 | 100.00% |
| board | igor_src_policy_de10_nano.v | v_line | 4 / 4 | 100.00% |
| board | igor_src_policy_de10_nano.v | v_toggle | 51 / 194 | 26.29% |
| board | igor_src_policy_uart.v | v_branch | 35 / 46 | 76.09% |
| board | igor_src_policy_uart.v | v_line | 37 / 47 | 78.72% |
| board | igor_src_policy_uart.v | v_toggle | 214 / 517 | 41.39% |
| board | igor_uart_rx.v | v_branch | 13 / 14 | 92.86% |
| board | igor_uart_rx.v | v_line | 8 / 10 | 80.00% |
| board | igor_uart_rx.v | v_toggle | 33 / 44 | 75.00% |
| board | igor_uart_tx.v | v_branch | 4 / 4 | 100.00% |
| board | igor_uart_tx.v | v_line | 5 / 5 | 100.00% |
| board | igor_uart_tx.v | v_toggle | 33 / 43 | 76.74% |
| core | igor_src_policy_core.v | v_branch | 96 / 96 | 100.00% |
| core | igor_src_policy_core.v | v_line | 68 / 68 | 100.00% |
| core | igor_src_policy_core.v | v_toggle | 870 / 908 | 95.81% |
| gate | igor_safety_security_gate.v | v_line | 13 / 13 | 100.00% |
| gate | igor_safety_security_gate.v | v_toggle | 102 / 107 | 95.33% |
| uart | igor_src_policy_core.v | v_branch | 95 / 96 | 98.96% |
| uart | igor_src_policy_core.v | v_line | 61 / 68 | 89.71% |
| uart | igor_src_policy_core.v | v_toggle | 829 / 908 | 91.30% |
| uart | igor_src_policy_uart.v | v_branch | 46 / 46 | 100.00% |
| uart | igor_src_policy_uart.v | v_line | 46 / 47 | 97.87% |
| uart | igor_src_policy_uart.v | v_toggle | 371 / 517 | 71.76% |
| uart | igor_uart_rx.v | v_branch | 14 / 14 | 100.00% |
| uart | igor_uart_rx.v | v_line | 9 / 10 | 90.00% |
| uart | igor_uart_rx.v | v_toggle | 31 / 44 | 70.45% |
| uart | igor_uart_tx.v | v_branch | 4 / 4 | 100.00% |
| uart | igor_uart_tx.v | v_line | 5 / 5 | 100.00% |
| uart | igor_uart_tx.v | v_toggle | 30 / 43 | 69.77% |

An absent metric is NOT MEASURED, never inferred as 0% or 100%.

Inventory definitions/checkpoints: 287. Inventory is not an executed-test count.

Pass-rate evidence (separate from code coverage):

| Suite | Passed / Executed | Pass rate |
| --- | ---: | ---: |
| Host | 29 / 29 | 100.00% |
| LiDAR | 16 / 16 | 100.00% |

Acceptance thresholds are project review criteria in ../../VERIFICATION_GUIDE.md; not ISO thresholds.
All emitted counter bins are included. Constant/unused bits remain visible in the raw toggle denominator.

## Explicit functional coverage models (separate from native code coverage)

| Model | Hit / Total | Percent |
| --- | ---: | ---: |
| Core FSM state_coverage | 8 / 8 | 100.00% |
| Core FSM normal_arc_coverage | 10 / 10 | 100.00% |
| Gate reachable modeled decision outcomes | 22 / 22 | 100.00% |

Functional models have explicit reviewed denominators; these are not native FSM/condition/MC-DC measurements. See individual JSON limitations.
