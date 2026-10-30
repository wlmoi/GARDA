# Fungsi setiap RTL dan hubungan dengan bukti

Acuan utama adalah policy PPO **74→128→64→3** pada README workspace. Tabel ini mencakup seluruh **22 file canonical `fpga/rtl/**/*.v`**, modul tambahan di dalam file tersebut, wrapper policy board dan dua komponen serializer motor. Source duplikat/arsip pada folder board tidak menjadi definisi arsitektur baru; QSF rilis menentukan source yang benar-benar dikompilasi. Daftar fungsi menjelaskan peran implementasi, bukan klaim seluruhnya terhubung menjadi satu jalur motor.

## Policy mengikuti software `src`

| RTL / modul | Fungsi dan kontrak | Bukti utama |
|---|---|---|
| [igor_src_policy_core.v](../rtl/igor_src_policy/igor_src_policy_core.v): `igor_src_policy_core` | Memuat 74 alamat observasi; bitmap menolak start tanpa input lengkap. FSM mengakses bias/weight ROM sinkron, menjalankan MAC serial 16×16/40-bit pada tiga layer, lalu menyimpan tiga residual. Menolak indeks/load/start invalid, mengabort hasil parsial, menghitung latency 54.348 siklus. | 236 vektor, seluruh hidden/output, malformed control dan abort; gambar 08. |
| File yang sama: `igor_src_policy_activation` | Floor signed accumulator/256; hidden ReLU saturasi [0,32767]; output clip [-256,256]. `saturated` menandai clipping hidden, bukan otomatis fault keselamatan. | 8.364 kasus aktivasi dan oracle integer. |
| [igor_src_policy_rom.v](../rtl/igor_src_policy/igor_src_policy_rom.v) | ROM baca sinkron, 18.051 parameter Q8.8 dan padding ke 32.768 word; diinferensikan ke M10K. Tidak melatih atau menghitung bobot di FPGA. | Provenance terhadap JSON dan enam MEM `src`; Fitter 64 M10K. |
| [igor_src_policy_uart.v](../rtl/igor_src_policy/igor_src_policy_uart.v) | Parser 153-byte/CRC Maxim, validasi 74 domain, buffer transaksi lengkap, load/start core, tangkap tiga aksi dan respons 11-byte. Mengelola E-stop, timeout, collision saat busy, lease residual, history fault serta counter accepted/rejected **saturating**. Permit berarti residual fresh/valid. | 184 transaksi/268 assertion; gambar 09–15; wrapper 18 checkpoint. |
| [igor_src_policy_de10_nano.v](../fpga_de10_nano/src_policy/igor_src_policy_de10_nano.v) | Top policy board: clock 50 MHz, reset, latch E-stop KEY1 sampai KEY0 reset, fabric UART dan LED debug. Bukan final motor gate. | Project `igor_src_policy.qpf`; wrapper actual-divider simulation; fitted 13 pins dan STA. |

## UART bersama

| RTL | Fungsi | Bukti / batas |
|---|---|---|
| [igor_uart_rx.v](../rtl/igor_uart_rx.v) | Sinkronisasi RX asynchronous dan FSM penerima UART 8N1; memberi `valid`, byte, dan framing error. | Decoder lawan pada UART policy, malformed stop bit, wrapper divider 54 dan regression legacy. Simulasi tidak mengukur metastabilitas fisik/MTBF. |
| [igor_uart_tx.v](../rtl/igor_uart_tx.v) | Serialisasi start bit, delapan data bit, stop bit, dan handshake busy. Cancellation policy memanfaatkan reset jalur TX. | Wire-level response decoder, CRC/header/output check, E-stop mid-TX. |

## Planner, peta dan safety gate legacy

| RTL | Fungsi | Bukti utama |
|---|---|---|
| [igor_top.v](../rtl/igor_top.v) | Mengorkestrasi config/map, empat rollout tile, selector dan gate. FSM IDLE/RUN/RESULT/FAULT; deadline/lease, binding result ke map sequence, latch penyebab abort dan logger. | Gambar 01–06; normal 7.938 siklus, E-stop/run/lease/map-version tests. |
| [igor_config_registers.v](../rtl/igor_config_registers.v) | Memvalidasi bit/versi/rentang konfigurasi dan batas v/omega/delta; mengunci konfigurasi; write saat locked/busy/konflik menyebabkan fault sticky. | Suite units dan malformed UART. |
| [igor_costmap_manager.v](../rtl/igor_costmap_manager.v) | Protokol begin→write in-order→complete→commit untuk dua bank peta. Memeriksa sequence, jumlah/alamat, konflik dan freshness; hanya commit sah menukar active bank. | Suite units/top: peta parsial, urutan salah, replay, commit saat busy, freshness tepat batas. |
| [igor_costmap_bank.v](../rtl/igor_costmap_bank.v) | RAM sinkron 32.768×8 menampung dua peta 128×128; tiap tile mempunyai replika RAM agar pembacaan paralel. | Fitter M10K dan rollout/costmap regression. Isi RAM belum sah sebelum commit tervalidasi. |
| [igor_candidate_generator.v](../rtl/igor_candidate_generator.v) | Memetakan indeks 9-bit menjadi v/omega dan menguji dynamic window terhadap previous v/omega serta batas absolut/delta. | Gate/unit arithmetic-domain boundary tests dan enam scene. |
| [igor_rollout_tile.v](../rtl/igor_rollout_tile.v) | Setiap tile memeriksa 128 kandidat dengan indeks `TILE_ID, TILE_ID+4, ...`; tiap kandidat 20 pose, RAM wait, occupancy/cost dan goal/velocity penalty. Menyimpan kandidat legal terbaik; tie-break indeks terkecil. Overflow/out-of-map membatalkan kandidat. | Enam scene, arithmetic/abort tests, fixed 7.938-cycle system latency pada konfigurasi default. Goal/start legacy ditetapkan di RTL; belum planner global generik. |
| [igor_kinematic_step.v](../rtl/igor_kinematic_step.v) | Langkah integrasi pose fixed-point x/y/heading menggunakan velocity, omega dan LUT sin/cos; menghasilkan flag overflow dan outside map. | Boundary arithmetic/unit/scene regression. Ini rollout gerak v/omega; bukan inverse kinematics empat roda holonomik. |
| [igor_trig_lut.v](../rtl/igor_trig_lut.v) | LUT sinus fixed-point 256 fase; cos diperoleh melalui pergeseran fase pada stepper. | Kinematic/rollout oracle dan scenes. |
| [igor_score_accumulator.v](../rtl/igor_score_accumulator.v) | Penjumlahan cost 32-bit dengan bit carry ke-33 sebagai overflow; total low-32 diteruskan beserta flag. Bukan saturating adder: pemakai wajib menolak overflow. | Numeric boundaries dan rollout arithmetic fault. |
| [igor_best_candidate_selector.v](../rtl/igor_best_candidate_selector.v) | Tournament dua tingkat memilih hasil valid terbaik empat tile; score terendah, lalu indeks terendah; tanpa valid hasil/output default nol. | Selector/tie-break/unit/scene tests. |
| [igor_safety_security_gate.v](../rtl/igor_safety_security_gate.v) | Gate kombinatorial default output nol; urutan prioritas reset→E-stop→protective→ready→map→config→arithmetic→timeout→result→absolute→delta. Hanya PASS meneruskan kandidat. | 111.210 oracle comparisons, 12 outcome; gambar 07. |
| [igor_status_logger.v](../rtl/igor_status_logger.v) | Mencatat last_fault dan counter 32-bit saturating ketika fault nonnol berubah; tidak menaikkan setiap clock dan menghitung recurrence setelah clear. Reset menghapus sejarah. | Units logger tests; pasangan E-stop assertion/clock log gambar 01. |
| [igor_uart_protocol.v](../rtl/igor_uart_protocol.v) | Framing legacy delapan byte A5…5A/CRC8 polynomial 0x07; timeout dan protocol_fault. Berbeda dari framing PPO/CRC Maxim. | 39 UART safety checkpoints serta legacy UART regression. |
| [igor_uart_top.v](../rtl/igor_uart_top.v) | Top board planner dengan UART: menolak reserved/payload invalid sebelum side effect, menghubungkan map/config/run, status/output/event/last_fault dan endpoint neural legacy. Opcode 9 planner cycles; 10/11 load/start neural; 12/13 neural output/cycles. | Fitted 17 pins, build planner, UART contract tests. Belum mengirim langsung paket motor STM32. |
| [igor_de10_nano_wrapper.v](../rtl/igor_de10_nano_wrapper.v) | Wrapper demo mandiri yang menyusun config dan peta skenario berdasarkan switch, memulai planner dan menampilkan status pada LED. | Wrapper legacy regression. Top aktif image planner UART adalah `igor_uart_top`, sehingga wrapper demo ini bukan entry point SOF rilis tersebut. |

## Neural legacy — model berbeda dari README

| RTL / modul | Fungsi | Bukti / batas |
|---|---|---|
| [igor_neural_core.v](../rtl/igor_neural_core.v): `igor_neural_core` | Menggabungkan ROM dan datapath model 24→64→64→4. | 100 vektor/400 output, 18.192 siklus; tidak menggantikan bukti PPO. |
| File yang sama: `igor_neural_datapath` | MAC integer dengan interface synchronous parameter-memory dan `weights_ready`; bitmap input lengkap, ReLU/clipping, done/fault/latency. | Integer oracle legacy. Interface memory memungkinkan jalur ASIC terpisah; bukan bukti chip ASIC diproduksi. |
| [igor_neural_rom.v](../rtl/igor_neural_rom.v) | ROM bobot legacy yang diinisialisasi dari aset model 24-input. | ROM inspection dan neural vectors; bukan ROM PPO 18.051 word. |

## Komponen pengirim motor yang masih terpisah

| RTL | Fungsi | Bukti / batas |
|---|---|---|
| [stm_packet_tx_multispeed.v](../robot/jetauto/FPGA_UART_TTL_MULTISPEED/rtl/stm_packet_tx_multispeed.v) | Menyusun dan menserialisasi frame STM32 multi-motor, nilai speed/float, ID dan CRC sesuai fixture. | 10 frame/256 byte, four-speed/both-direction/all-ID decode, offline. |
| [stm_uart_multispeed_top.v](../robot/jetauto/FPGA_UART_TTL_MULTISPEED/rtl/stm_uart_multispeed_top.v) | Controller arm/refresh/lease dan urutan perintah/STOP untuk serializer tersebut. | Test controller offline. Belum disambungkan menjadi satu-satunya jalur actuator dari gate utama. |

Untuk melihat RTL mana yang benar-benar masuk SOF, baca `VERILOG_FILE` dalam QSF dan `source_sha256` pada receipt build. File `.gtkw` bukan RTL; ia hanya menyimpan daftar sinyal/format/zoom. VCD berasal dari simulasi. [SIMULATION_EVIDENCE](SIMULATION_EVIDENCE.md) menjelaskan titik dan alasan PASS; [RTL_IMPROVEMENTS](RTL_IMPROVEMENTS.md) membedakan perbaikan yang sudah lulus dari usulan.
