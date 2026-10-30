# Top module dan breakdown RTL

## Top yang dipilih

| Target | Top module | File |
|---|---|---|
| DE10-Nano | garda_uart_top | [RTL](../fpga_de10_nano/rtl/garda_uart_top.v) |
| DE10-Lite | garda_de10_lite_top | [RTL](../fpga_de10_lite/rtl/garda_de10_lite_top.v) |
| TinyTapeout aktif | tt_um_wlmoi_garda_neural_logic | [Inferensi lengkap](../src/garda_neural_logic_top.v) |
| TinyTapeout legacy | tt_um_wlmoi_garda_gate | [Wrapper](../src/project.v) |
| STM single speed | stm_uart_demo_top | [RTL](../robot/jetauto/FPGA_UART_TTL/rtl/stm_uart_demo_top.v) |
| STM four speed | stm_uart_multispeed_top | [RTL](../robot/jetauto/FPGA_UART_TTL_MULTISPEED/rtl/stm_uart_multispeed_top.v) |

## Seluruh modul common accelerator

| Modul | Fungsi |
|---|---|
| [garda_uart_top](../rtl/garda_uart_top.v) | Top DE10-Nano, UART dispatch dan readback neural |
| [garda_uart_protocol](../rtl/garda_uart_protocol.v) | Framing request/response delapan byte dan command dispatch |
| [garda_uart_rx](../rtl/garda_uart_rx.v) | Receiver UART |
| [garda_uart_tx](../rtl/garda_uart_tx.v) | Transmitter UART |
| [garda_top](../rtl/garda_top.v) | Kontrol DWA, hasil, deadline, dan gerbang output |
| [garda_config_registers](../rtl/garda_config_registers.v) | Konfigurasi 32 bit, limit, validity, dan lock |
| [garda_costmap_manager](../rtl/garda_costmap_manager.v) | Sequence, upload order, frame completion, commit, freshness |
| [garda_costmap_bank](../rtl/garda_costmap_bank.v) | Memory synchronous 32768 × 8, dua frame per copy |
| [garda_candidate_generator](../rtl/garda_candidate_generator.v) | Enumerasi velocity dan angular-rate kandidat |
| [garda_rollout_tile](../rtl/garda_rollout_tile.v) | 128 kandidat dan 20 pose pada satu evaluator |
| [garda_kinematic_step](../rtl/garda_kinematic_step.v) | Update posisi serta heading fixed-point |
| [garda_trig_lut](../rtl/garda_trig_lut.v) | Lookup sinus dan cosinus signed |
| [garda_score_accumulator](../rtl/garda_score_accumulator.v) | Akumulasi critic 32 bit |
| [garda_best_candidate_selector](../rtl/garda_best_candidate_selector.v) | Pemilihan empat hasil tile dan tie-break |
| [garda_safety_security_gate](../rtl/garda_safety_security_gate.v) | Pemeriksaan permit dan pembatasan command |
| [garda_status_logger](../rtl/garda_status_logger.v) | Fault 8 bit dan event counter 32 bit |
| [garda_neural_core](../rtl/garda_neural_core.v) | MAC serial signed 16 bit, accumulator 40 bit |
| [garda_neural_rom](../rtl/garda_neural_rom.v) | ROM bobot dan bias, address 13 bit |
| [garda_de10_nano_wrapper](../rtl/garda_de10_nano_wrapper.v) | Wrapper scene alternatif, bukan UART top aktif |

Root `rtl/` digunakan oleh regresi. Kedua project FPGA mempunyai copy source untuk menjaga folder board portable. Lite menggunakan atribut RAM M9K pada costmap/ROM serta wrapper MAX 10 sendiri. Nano menggunakan M10K dan wrapper Cyclone V. Validator memeriksa perbedaan target yang spesifik ini. Perubahan common RTL harus disinkronkan ke copy board, kemudian diverifikasi serta dibuild ulang.

Detail bit flow ada pada [ARCHITECTURE.md](ARCHITECTURE.md). Detail FSM dan setiap modul tersedia dalam [Flowchart 28 halaman](flowcharts/GARDA_RTL_Flowchart.io).
