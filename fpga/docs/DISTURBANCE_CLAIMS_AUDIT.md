# Audit implementasi dan pengujian: 18 intelligent disturbances GARDA

Tanggal: **20 Oktober 2026 (Asia/Jakarta)**. Branch: **bri/pipeline**. Commit dasar: `90fcd47b510bb00ded55a3283297f445bce65170`.

Objek audit: gambar pengguna berjudul **“18 intelligent disturbances: 11 verified, 7 closing next”**, berisi delapan label RTL, tiga Sim, dan tujuh Next. Semua 18 baris diperiksa di bawah. Gambar diperlakukan sebagai kumpulan klaim yang perlu dibuktikan, bukan instruksi untuk membuat hasil PASS.

**Kesimpulan:** sejumlah mekanisme dan test digital memang tersedia dan berhasil diulang. Namun, judul **“11 verified” belum dapat disahkan sebagai 11 uji gangguan lengkap**. Bukti digital CRC tidak setara dengan uji cairan/EMI; clamp bukan detektor spoofing; fixed core latency bukan hasil uji jitter OS. Klaim training lag **5–15 ms**, STM32 memutus PWM setelah **200 ms**, serta uji lantai basah dengan PID tidak memiliki bukti implementasi/pengujian lengkap yang ditemukan pada checkout ini.

Audit ini hanya menambah dokumen. Tidak menambahkan fitur atau test baru, tidak memprogram board, tidak membuka serial, tidak menggerakkan robot, dan **tidak di-commit atau dipush**.

## 1. Cara menilai bukti

Empat hal dibedakan: **kode mekanisme ada**, **test yang menyasar mekanisme ada**, **test dijalankan dan lulus**, dan **gangguan fisik pada slide benar-benar diuji**. Tiga hal pertama tidak otomatis membuktikan yang keempat.

- **Ada + diuji**: mekanisme tertentu dan assertion terkait ditemukan; cakupan yang dibuktikan disebutkan.
- **Sebagian**: hanya sebagian respons, hanya proxy digital, atau implementasi berada di modul lain dari yang diiklankan.
- **Tidak ditemukan**: tidak ditemukan implementasi/test yang sesuai klaim spesifik pada source yang diperiksa. Ini bukan pernyataan tentang firmware tertutup atau pekerjaan di branch lain.
- **Next**: slide sendiri menandainya roadmap; ketiadaan fitur tersebut tidak dicatat sebagai klaim selesai palsu.

Tiga arsitektur dalam repo tidak boleh digabung menjadi satu chip yang telah diuji end-to-end:

1. **Parallel8 neural FPGA**: `fpga/experiments/parallel8`, top `garda_src_policy_de10_nano`, output residual Q8.8 melalui UART. QSF memuat core, UART dan wrapper; **tidak memuat planner gate/costmap**. Wrapper menyatakan tidak ada motor driver di top ini.
2. **Planner/gate FPGA**: `fpga/rtl/garda_top.v`, `garda_safety_security_gate.v`, costmap, logger dan protocol planner. Sumber angka 111.210 vektor.
3. **ASIC protocol engine**: `src/gardachip_top.v`, top `tt_um_gardachip`, empat context, pin mask dan program memory. Sumber bukti isolasi I/O/lock program; bukan neural Parallel8.

Host integrasi yang diuji memakai `fpga/software_integration/src`, sedangkan `src/garda_*` adalah reference asli. Perbedaan ini ditandai saat mengutip source. Beberapa perubahan FPGA lokal sudah ada sebelum audit; tidak diubah oleh audit ini. SHA-256 source yang dikutip disertakan di akhir.

## 2. Matriks seluruh klaim

| No. | Disturbance / label slide | Implementasi ditemukan | Test spesifik yang ada | Penilaian terhadap kalimat slide |
|---|---|---|---|---|
| 1 | Worker steps in close / Sim | Zero-stop pada simulator dan host | Host critical-distance/CBF fixture | **Sebagian:** stop command terbukti, bukan pekerja nyata atau stopping distance fisik. |
| 2 | Operator hits E-stop / RTL | Guard residual, latch/error, gate planner | Wrapper KEY1 + gate/top E-stop | **Sebagian:** output digital nol/log terbukti; top neural tidak langsung menolkan PWM motor. |
| 3 | AI surges near cargo / RTL | Envelope dan scaling software; limit generic planner | Host final-envelope fixture | **Sebagian/salah cakupan:** 0,15 bukan batas maju global RTL. |
| 4 | Load shifts in a turn / Next | Clamp dan wheel-slip randomization | Test clamp ada; test perpindahan beban/OOD tidak ditemukan | Roadmap; bukan verifikasi perubahan massa/CoM. |
| 5 | Facility blackout / RTL | Map freshness dan fault gate | Exact map-stale boundary + host sensor stale | **Sebagian:** stale data diuji; blackout dan LiDAR di gelap tidak diuji. |
| 6 | Liquid on wiring / RTL | CRC, framing dan timeout | Corrupted frame/trailer/truncation tests | **Sebagian:** model korupsi digital, tidak ada uji cairan/korsleting. |
| 7 | Wet, oily floor / Sim | Timer nominal 50 Hz; slip model simulator | Tidak ditemukan acceptance lantai basah + wheel PID | **Sebagian:** simulator slip ada; PID motor tertutup tidak dibuktikan. |
| 8 | Battery brownout / Next | Host command watchdog 0,5 s; bukan brownout detector | Tidak ditemukan test PWM cutoff STM 200 ms | **Tidak ditemukan** untuk klaim 200 ms; tetap roadmap. |
| 9 | Press-line EMI / RTL | CRC-8 dan frame rejection | Bad CRC/framing/glitch | **Sebagian:** parser diuji; tidak ada uji EMC/EMI fisik. |
| 10 | Host OS jitter / RTL | Fixed 6.916 core cycles | 236 network vectors + latency assertions | **Ada + diuji untuk core**; bukan end-to-end host jitter. |
| 11 | Serial latency spike / Sim | Host deadline check | Fixture slow read/write 21 ms | **Tidak ditemukan** training lag 5–15 ms. Deadline test berbeda. |
| 12 | Sensor hangs I²C bus / Next | Context scheduler, wait pin, open drain | Finite stretch, NACK, concurrent contexts | **Sebagian sudah ada**; permanent stuck-bus isolation/recovery test tidak ditemukan. |
| 13 | Two drivers, one pin / Next | Conflict pin-mask rejected; sticky error bits | Explicit overlap rejection/release test | **Ada + diuji** pada ASIC protocol engine, bukan FPGA neural. |
| 14 | LiDAR or IMU spoofing / RTL | Input domain check; action clamp ±256 Q8.8 | Activation vectors + invalid-domain host tests | **Sebagian:** membatasi angka; tidak mendeteksi spoof yang masih valid domain. |
| 15 | Serial frame replay / Next | Planner map sequence check | Map replay test | **Sebagian:** anti-replay map ada; neural UART sequence/HMAC tidak ditemukan. |
| 16 | Weight tampering / RTL | Neural weights dibaca dari ROM tanpa write port runtime | Bank/provenance dan bit-exact tests | **Ada secara struktur**; belum test serangan modifikasi bobot/bitstream. |
| 17 | Hacked host rewrites I/O / Next | Program write disabled ketika core enabled | Live write rejection test | **Sebagian sudah ada:** program lock, bukan akses host terautentikasi atau lock semua I/O. |
| 18 | Tampered bitstream / Next | SHA-256 manifest dan checker file | Test helper hash/link; test bitstream tamper/secure boot tidak ditemukan | **Sebagian:** integritas file di host, bukan authenticated configuration. |

## 3. Bukti kode dan test per klaim

### 1 — Worker steps in close → hard stop under 0,22 m

**Kode ada.** Simulator training menolkan seluruh body command saat jarak minimum di bawah 0,22 m. Ini aksi simulator, belum pengukuran jarak berhenti kendaraan.

Sumber: [src/garda_navigation/garda_navigation/retrain_ai.py:377](D:/LinkedinProjects/garda_ws/garda_ws/src/garda_navigation/garda_navigation/retrain_ai.py:377) (baris 377–379).

```python
        if d_min < 0.22:
            v_body_x, v_body_y, w_body = 0.0, 0.0, 0.0

```
Host integrasi juga memiliki final override yang berlaku sesudah inferensi/filter, sebelum kinematika roda:

Sumber: [fpga/software_integration/src/garda_controller/garda_controller/controller_node.py:384](D:/LinkedinProjects/garda_ws/garda_ws/fpga/software_integration/src/garda_controller/garda_controller/controller_node.py:384) (baris 384–388).

```python
        if d_min <= 0.22 or not np.any(command):
            v_safe = np.zeros(3, dtype=np.float32)
        else:
            v_safe = np.clip(v_safe, [-0.15, -0.50, -2.0], [allowed_max_vx, 0.50, 2.0])

```
**Test tersedia dan lulus ulang:** [fpga/verification/run_host_regression.py:226](D:/LinkedinProjects/garda_ws/garda_ws/fpga/verification/run_host_regression.py:226) dan `test_scan_metadata_and_positive_infinity_no_return`. Fixture membuktikan command empat roda nol ketika obstacle kritis ada; tidak memakai worker/robot nyata. Test batas kritis ini bukan coverage exhaustif seluruh jarak atau noise LiDAR.

**Tidak ditemukan:** test “worker steps in close” dengan lintasan manusia, rekaman robot, speed sebelum stop, stopping time/distance dan kriteria penerimaannya. Label yang aman: **critical-distance zero command tested in simulator/host fixtures**.

### 2 — Operator hits E-stop → FPGA zeroes motors, logs a fault

**Guard dan error memang ada** pada neural UART:

Sumber: [fpga/rtl/garda_src_policy/garda_src_policy_uart.v:96](D:/LinkedinProjects/garda_ws/garda_ws/fpga/rtl/garda_src_policy/garda_src_policy_uart.v:96) (baris 96–100).

```verilog
    assign safety_permit=result_valid && !estop_active && !core_fault;
    assign action0=safety_permit ? sample0 : 16'sd0;
    assign action1=safety_permit ? sample1 : 16'sd0;
    assign action2=safety_permit ? sample2 : 16'sd0;
    assign debug_state=estop_active ? 4'hf : (core_fault ? 4'he : mode);
```

Sumber: [fpga/rtl/garda_src_policy/garda_src_policy_uart.v:109](D:/LinkedinProjects/garda_ws/garda_ws/fpga/rtl/garda_src_policy/garda_src_policy_uart.v:109) (baris 109–115).

```verilog
            error_code<=code; error_history<=error_history | (12'h1 << (code[3:0]-1'b1));
            // Audit counters saturate: long-running faults must never look like
            // a fresh/reset device after wrapping through zero.
            if (rejected_frames!=32'hffffffff)
                rejected_frames<=rejected_frames+1'b1;
            result_valid<=0; position<=0; mode<=RX;
            rx_timer<=0; infer_timer<=0;
```
**Test tersedia dan lulus ulang:** [fpga/experiments/parallel8/tb_board_wrapper.sv:78](D:/LinkedinProjects/garda_ws/garda_ws/fpga/experiments/parallel8/tb_board_wrapper.sv:78) sampai pengujian latch, history dan reset. Wrapper memiliki **18 checkpoint**. Planner juga menguji fault code 2, command nol dan logger:

Sumber: [fpga/verification/tb_safety_top.v:59](D:/LinkedinProjects/garda_ws/garda_ws/fpga/verification/tb_safety_top.v:59) (baris 59–61).

```verilog
 result_ready;events_before=event_count;#3;estop=1;zero_outputs(2);checkpoint("estop_asserted_between_clocks_immediate_zero");
 tick;if(last_fault!=2 || event_count!=events_before+1)$fatal(1,"estop log");checkpoint("estop_registered_error_log");
 @(negedge clk);estop=0;tick;zero_outputs(2);checkpoint("estop_release_requires_reset");
```
**Batas penting:** wrapper Parallel8 memberi residual `action0..2`, bukan kabel motor/PWM. Source top bahkan mencatat “No motor driver is connected here”. Jadi kalimat **“FPGA zeroes motors” terlalu luas** untuk image neural ini. Yang terbukti: residual digital nol, permit ditarik, error tercatat; jalur host/STM dan penghentian motor fisik perlu bukti terpisah.

### 3 — AI surges near cargo → forward capped at 0,15 m/s

**0,15 ada pada software, bukan aturan RTL universal.** Dalam simulator, scaling action maju positif adalah tambahan residual:

Sumber: [src/garda_navigation/garda_navigation/retrain_ai.py:360](D:/LinkedinProjects/garda_ws/garda_ws/src/garda_navigation/garda_navigation/retrain_ai.py:360) (baris 360–362).

```python
        delta_vx = a0 * self.max_cmd_vx if a0 < 0.0 else a0 * 0.15
        delta_vy = a1 * self.delta_vy_max
        delta_omega = a2 * self.delta_omega_max
```
Pada host integrasi, batas tergantung jarak:

Sumber: [fpga/software_integration/src/garda_controller/garda_controller/controller_node.py:326](D:/LinkedinProjects/garda_ws/garda_ws/fpga/software_integration/src/garda_controller/garda_controller/controller_node.py:326) (baris 326–327).

```python
        allowed_max_vx = float(np.interp(d_min, [0.22, 0.40, 1.20], [0.0, 0.15, 0.60]))

```

Sumber: [fpga/software_integration/src/garda_controller/garda_controller/controller_node.py:387](D:/LinkedinProjects/garda_ws/garda_ws/fpga/software_integration/src/garda_controller/garda_controller/controller_node.py:387) (baris 387–387).

```python
            v_safe = np.clip(v_safe, [-0.15, -0.50, -2.0], [allowed_max_vx, 0.50, 2.0])
```
Envelope 0,22–0,40 m memberi batas dari nol hingga 0,15 m/s; pada 0,80 m batasnya **0,375 m/s**, dan pada 1,20 m mencapai 0,60 m/s. Jadi ini bukan “semua forward capped 0,15”.

**Test tersedia dan lulus ulang:** [fpga/verification/run_host_regression.py:233](D:/LinkedinProjects/garda_ws/garda_ws/fpga/verification/run_host_regression.py:233) secara eksplisit mengharapkan 0,375 m/s pada 0,8 m. Planner RTL memiliki `max_v/max_dv`, tetapi tidak langsung mengartikan objek “cargo” atau unit m/s dari kalimat ini.

**Tidak ditemukan:** test RTL khusus AI surge dekat cargo yang membuktikan batas fisik 0,15 m/s pada semua kondisi. Klaim perlu menyebut **software distance-dependent speed envelope**.

### 4 — Load shifts in a turn → bounded fixes; OOD check next

**Bounded action ada** melalui clamp yang ditunjukkan pada nomor 3 dan 14. Simulator juga memodelkan perbedaan slip roda:

Sumber: [src/garda_navigation/garda_navigation/retrain_ai.py:270](D:/LinkedinProjects/garda_ws/garda_ws/src/garda_navigation/garda_navigation/retrain_ai.py:270) (baris 270–271).

```python
            self.wheel_slip_factors = np.random.uniform(0.90, 1.10, size=4).astype(np.float32)
            self.obstacles.append(DynamicObstacle([1.8, np.random.uniform(-0.5, 0.5)], radius=0.20))
```

Sumber: [src/garda_navigation/garda_navigation/retrain_ai.py:396](D:/LinkedinProjects/garda_ws/garda_ws/src/garda_navigation/garda_navigation/retrain_ai.py:396) (baris 396–398).

```python
        eff_rps = motor_rps * self.wheel_slip_factors if self.domain_randomization_enabled else motor_rps
        v_tang = eff_rps * self.wheel_circ
        real_body_vx = float((v_tang[0] + v_tang[1] + v_tang[2] + v_tang[3]) / 4.0)
```
Namun variasi slip bukan model perpindahan massa atau center of mass saat belok. Tidak ditemukan model load-shift/CoM, detector OOD, threshold OOD, atau test khusus beban berpindah. Test clamp yang lulus membuktikan pembatasan nilai, bukan kestabilan dengan perubahan beban. Karena slide berlabel **Next**, pertahankan sebagai roadmap; tidak perlu diimplementasikan untuk audit ini.

### 5 — Facility blackout → LiDAR works dark; stale map stops

**Map-stale stop ada pada planner**:

Sumber: [fpga/rtl/garda_costmap_manager.v:17](D:/LinkedinProjects/garda_ws/garda_ws/fpga/rtl/garda_costmap_manager.v:17) (baris 17–17).

```verilog
assign fresh=valid && age<FRESH_CYCLES;
```

Sumber: [fpga/rtl/garda_safety_security_gate.v:24](D:/LinkedinProjects/garda_ws/garda_ws/fpga/rtl/garda_safety_security_gate.v:24) (baris 24–24).

```verilog
 else if (!map_ok) fault_code=8'd5;
```
Test mengunci kondisi tepat di ambang freshness dan memeriksa fault/log:

Sumber: [fpga/verification/tb_safety_top.v:71](D:/LinkedinProjects/garda_ws/garda_ws/fpga/verification/tb_safety_top.v:71) (baris 71–71).

```verilog
 wait(freshness_core.maps.age==10000);#1;if(stale_enable || stale_fault!=5)$fatal(1,"stale map exact cutoff");checkpoint_source=2;checkpoint("map_freshness_exact_boundary_zero");tick;if(stale_last!=5)$fatal(1,"stale map log");checkpoint("map_freshness_zero_and_logged");checkpoint_source=0;
```
**Test tersedia dan lulus ulang:** `map_freshness_exact_boundary_zero`, `map_freshness_zero_and_logged`; host [fpga/verification/run_host_regression.py:200](D:/LinkedinProjects/garda_ws/garda_ws/fpga/verification/run_host_regression.py:200) juga lulus. Test planner memakai `FRESH_CYCLES=10000` untuk mempercepat boundary test; itu bukan bukti seluruh deployment memakai ambang sama.

**Tidak ditemukan:** power-off fasilitas, pengukuran LiDAR dalam gelap, suplai cadangan, atau uji robot saat blackout. Map planner juga tidak otomatis berada dalam source list top neural Parallel8. Klaim yang terbukti hanya **freshness failure retracts digital permit/commands**.

### 6 — Liquid on wiring → corrupt frames rejected

**Parser korupsi ada**, termasuk CRC, trailer, frame terpotong dan stop bit. Contoh test:

Sumber: [fpga/verification/tb_safety_uart.v:52](D:/LinkedinProjects/garda_ws/garda_ws/fpga/verification/tb_safety_uart.v:52) (baris 52–53).

```verilog
 reset_all;send_frame(7,0,1,0);if(!dut.protocol_fault || accepted_count!=0 || dut.enable || dut.last!=4)$fatal(1,"bad crc");checkpoint("crc_corruption_zero_and_logged");
 send_frame(4,32'h00143d0f,0,0);if(accepted_count!=0 || dut.core.cfg.valid)$fatal(1,"protocol sticky bypass");checkpoint("good_command_after_crc_fault_rejected");
```
Test tersedia dan lulus ulang dalam suite safety UART, bersama `wrong_terminator_rejected`, `truncated_frame_timeout`, dan `uart_stop_bit_error` ([fpga/verification/tb_safety_uart.v:54](D:/LinkedinProjects/garda_ws/garda_ws/fpga/verification/tb_safety_uart.v:54)).

**Tidak ditemukan:** injeksi cairan, resistansi bocor, korsleting, overvoltage atau electrical isolation test. Mengubah byte dalam testbench bukan simulasi lengkap rangkaian yang terkena cairan. Bukti ini hanya mendukung **malformed/corrupted digital frame rejection**.

### 7 — Wet, oily floor → 50 Hz closed loop + wheel PID

**Timer host 50 Hz ada**:

Sumber: [fpga/software_integration/src/garda_controller/garda_controller/controller_node.py:59](D:/LinkedinProjects/garda_ws/garda_ws/fpga/software_integration/src/garda_controller/garda_controller/controller_node.py:59) (baris 59–59).

```python
        self.declare_parameter('control_rate_hz', 50.0)
```

Sumber: [fpga/software_integration/src/garda_controller/garda_controller/controller_node.py:194](D:/LinkedinProjects/garda_ws/garda_ws/fpga/software_integration/src/garda_controller/garda_controller/controller_node.py:194) (baris 194–195).

```python
        timer_period = 1.0 / self.control_rate_hz
        self.timer = self.create_timer(timer_period, self._control_loop)
```
**Slip simulator ada**, tetapi bukan plant PID motor: simulator menghitung kecepatan dari RPS yang dikalikan faktor slip lalu langsung mengintegrasikan pose. Frekuensi simulasi training juga berbeda:

Sumber: [src/garda_navigation/garda_navigation/retrain_ai.py:126](D:/LinkedinProjects/garda_ws/garda_ws/src/garda_navigation/garda_navigation/retrain_ai.py:126) (baris 126–126).

```python
        self.dt = 0.033
```
`dt=0,033` berarti sekitar **30,3 Hz**, bukan 50 Hz. Angka 50 Hz adalah timer node host.

**Tidak ditemukan:** source firmware STM32 motor PID, parameter/tuning PID, encoder-feedback test untuk kasus basah/berminyak, model koefisien gesek yang divalidasi, atau hasil acceptance wet-floor. Uji pengiriman RPS dan wheel bergerak tidak cukup membuktikan tuning/stabilitas PID pada permukaan tersebut. File review motor repo juga membedakan utilitas PID host dari firmware PID STM.

Klaim **“Sim verified wet/oily floor + wheel PID” belum terbukti lengkap**. Yang dapat diklaim: **nominal 50 Hz host loop; wheel-slip randomization available in simulation**.

### 8 — Battery brownout → STM32 cuts PWM after 200 ms

**Tidak ditemukan implementasi/test sesuai kalimat ini** pada source firmware yang tersedia. Repo berisi host driver dan RTL serializer; itu bukan source firmware watchdog/brownout STM32.

Watchdog host yang nyata memakai **0,5 s**:

Sumber: [fpga/software_integration/src/garda_controller/garda_controller/controller_node.py:252](D:/LinkedinProjects/garda_ws/garda_ws/fpga/software_integration/src/garda_controller/garda_controller/controller_node.py:252) (baris 252–258).

```python
        # Watchdog: if no command received for > 0.5s, command zero
        if not 0.0 <= now - command_time < 0.5:
            self.cmd_linear_x = 0.0
            self.cmd_linear_y = 0.0
            self.cmd_angular_z = 0.0
            self._stop_for_fault("COMMAND_STALE")
            return
```
Test [fpga/verification/run_host_regression.py:197](D:/LinkedinProjects/garda_ws/garda_ws/fpga/verification/run_host_regression.py:197) lulus ulang, tetapi memeriksa keputusan software mengirim nol. Itu tidak membuktikan timer STM32 200 ms, apalagi respons tegangan turun.

Nilai `join(timeout=0.2)` yang ditemukan pada driver terkait menunggu thread saat shutdown, **bukan** cutoff PWM. Brownout detector tegangan dan watchdog komunikasi adalah mekanisme berbeda. Dokumen [fpga/robot/jetauto/FPGA_VERILOG_TUTORIAL.md:99](D:/LinkedinProjects/garda_ws/garda_ws/fpga/robot/jetauto/FPGA_VERILOG_TUTORIAL.md:99) menyatakan belum ada verifikasi STM watchdog pada RTL demo.

Status **Next** tepat; angka **200 ms belum boleh dianggap hasil yang sudah diverifikasi**.

### 9 — Press-line EMI → CRC-8 drops corrupted frames

CRC source-policy memang memicu reject:

Sumber: [fpga/rtl/garda_src_policy/garda_src_policy_uart.v:173](D:/LinkedinProjects/garda_ws/garda_ws/fpga/rtl/garda_src_policy/garda_src_policy_uart.v:173) (baris 173–176).

```verilog
                            if (rx_data!=crc) reject(8'd6);
                            else if (invalid_observation) reject(8'd8);
                            else begin
                                if (accepted_frames!=32'hffffffff)
```
**Test tersedia dan lulus ulang:** CRC corruption suite safety dan [test/test_rtl.py:206](D:/LinkedinProjects/garda_ws/garda_ws/test/test_rtl.py:206), `test_uart_rx_start_glitch_and_valid_frame`. CRC diuji pada model paket digital. Bukti nomor 6 dan 9 banyak memakai mekanisme/test yang sama; tidak otomatis dua kampanye uji fisik terpisah.

**Tidak ditemukan:** RF/conducted injection, EFT/burst, ESD, medan motor/press-line, amplitudo/frekuensi/durasi, atau hasil EMC di setup fisik. CRC juga bukan autentikasi: pengirim yang menghitung ulang CRC dapat membuat paket palsu yang valid. Klaim aman: **CRC/framing rejects the tested digital corruption cases**.

### 10 — Host OS jitter → fixed 138,32 µs on FPGA

Testbench menegakkan latency untuk setiap network vector:

Sumber: [fpga/experiments/parallel8/tb_src_policy_core.sv:102](D:/LinkedinProjects/garda_ws/garda_ws/fpga/experiments/parallel8/tb_src_policy_core.sv:102) (baris 102–104).

```verilog
            if(fault||busy||latency_cycles!==6916)
                $fatal(1,"Vector %0d: bad completion fault=%0d latency=%0d",vector_id,fault,latency_cycles);
            if(saturated!==expected_sat[vector_id])$fatal(1,"Vector %0d saturation diagnostic mismatch",vector_id);
```
**Diulang dan lulus:** 236 network vectors, 8.364 activation cases, 54.399 assertions. Semua hidden activations dan tiga output dibandingkan oracle. Pada clock 50 MHz:

`6916 / 50.000.000 = 0,00013832 s = 138,32 µs = 0,13832 ms`.

**Benar untuk core setelah start diterima.** Waktu antrian host, USB, transfer UART request/response, validasi, dan pengiriman motor tidak termasuk. Tidak ditemukan eksperimen stress/jitter scheduler OS dengan distribusi end-to-end latency. Jadi kalimat slide dapat dipakai bila jelas berbunyi **fixed neural-core execution time**, bukan total response time terhadap semua jitter.

### 11 — Serial latency spike → trained with 5–15 ms lag

**Tidak ditemukan implementasi training lag 5–15 ms** di `retrain_ai.py` reference maupun mirror integrasi: tidak ditemukan queue aksi tertunda, sampling delay rentang tersebut, atau laporan eksperimen training yang mengikat model saat ini ke parameter lag itu. `latency_ms` yang disimpan pada evaluasi adalah pengukuran waktu komputasi, bukan injeksi delay training.

Test yang benar-benar ada adalah deadline host:

Sumber: [fpga/verification/run_host_regression.py:114](D:/LinkedinProjects/garda_ws/garda_ws/fpga/verification/run_host_regression.py:114) (baris 114–120).

```python
    def test_total_deadline_rejects_slow_write_and_slow_read(self):
        for clock_values in ([10.,10.021],[10.,10.001,10.021]):
            b=hardware_fixture()
            with patch.object(bridge.time,'monotonic',side_effect=clock_values):
                with self.assertRaises(bridge.FPGACommunicationError): b.infer(self.obs)
            self.assertFalse(b.last_exchange_ok)

```
Fixture ini menguji waktu 21 ms pada write/read dengan clock yang dimock. **Lulus ulang**, tetapi bukan pembuktian training 5–15 ms dan bukan uji toleransi spike serial fisik. Klaim training pada slide perlu ditandai **belum ditemukan/belum terbukti**, bukan diberi status verified berdasarkan deadline test.

### 12 — Sensor hangs the I²C bus → each I/O context isolated

Scheduler ASIC memberi context lain kesempatan walau context saat ini menunggu pin:

Sumber: [src/gardachip_top.v:134](D:/LinkedinProjects/garda_ws/garda_ws/src/gardachip_top.v:134) (baris 134–137).

```verilog
    slot <= slot + 2'd1;
    if (!halted[slot]) begin
     if (wait_count[slot] != 0) wait_count[slot] <= wait_count[slot] - 8'd1;
     else begin
```

Sumber: [src/gardachip_top.v:178](D:/LinkedinProjects/garda_ws/garda_ws/src/gardachip_top.v:178) (baris 178–178).

```verilog
        1: if (!pin_ready) pc[slot] <= active_pc;
```
**Test tersedia dan lulus ulang:** [test/test_rtl.py:274](D:/LinkedinProjects/garda_ws/garda_ws/test/test_rtl.py:274), `test_i2c_nack_stops_before_data`, `test_four_protocol_contexts_concurrently`. Test stretch menahan SCL **30 siklus**, lalu melepasnya; bukan stuck selamanya.

**Belum ditemukan:** test yang menahan SDA/SCL secara permanen sekaligus memeriksa kemajuan context lain dan batas waktunya, prosedur bus recovery, atau uji sensor fisik hang. Isolation scheduler dasarnya ada dan concurrency diuji; klaim permanent-hang lengkap tetap **Next/partial**. Ini fitur protocol engine ASIC, bukan jalur LiDAR USB pada Parallel8.

### 13 — Two drivers, one pin → pin mask rejects and logs it

Implementasi menolak pin-mask overlap dan menandai error context:

Sumber: [src/gardachip_top.v:124](D:/LinkedinProjects/garda_ws/garda_ws/src/gardachip_top.v:124) (baris 124–128).

```verilog
      if (!core_enabled && !(|(host_data & other_pins))) begin
       pin_mask[host_tid] <= host_data;
       output_oe_q <= output_oe_q & ~pin_mask[host_tid];
      end else errors[host_tid] <= 1;
     end
```
Test secara eksplisit mencoba konflik dan memastikan mask lama tidak tertimpa:

Sumber: [test/test_rtl.py:347](D:/LinkedinProjects/garda_ws/garda_ws/test/test_rtl.py:347) (baris 347–354).

```python
    def test_pin_ownership_rejects_overlap_and_releases_old_mask(self):
        after = """
          wr(0, 0); wr(5, 1); wr(10, 1);
          rd(10, value); if(value !== 2) $fatal(1,"overlap accepted");
          rd(1, value); if(!value[5]) $fatal(1,"overlap error missing");
          wr(5, 0); wr(10, 4);
          if(dut.output_oe_q[0]) $fatal(1,"old ownership still driving");
          rd(10, value); if(value !== 4) $fatal(1,"new mask missing");
```
**Lulus ulang.** Buktinya sudah melampaui sekadar roadmap untuk pemeriksaan konflik mask pada ASIC protocol engine.

Arti “logs it” di sini adalah **sticky bit `errors[host_tid]` yang bisa dibaca host**, bukan timestamped event logger dengan penyimpanan historis. Mekanisme ini tidak mendeteksi dua perangkat eksternal yang secara fisik terlanjur mendorong satu pin.

### 14 — LiDAR or IMU spoofing → outputs clamped to ±1,0 in RTL

Clamp output layer pada Parallel8 benar-benar ada:

Sumber: [fpga/experiments/parallel8/garda_src_policy_core.v:15](D:/LinkedinProjects/garda_ws/garda_ws/fpga/experiments/parallel8/garda_src_policy_core.v:15) (baris 15–20).

```verilog
    assign value = output_layer ?
        (scaled > 32'sd256 ? 16'sd256 :
        (scaled < -32'sd256 ? -16'sd256 : scaled[15:0])) :
        (scaled < 0 ? 16'sd0 :
        (scaled > 32'sd32767 ? 16'sd32767 : scaled[15:0]));
endmodule
```
±256 Q8.8 = ±1,0 normalized. Test activation menguji data pembatasan dan perbandingan oracle:

Sumber: [fpga/experiments/parallel8/tb_src_policy_core.sv:89](D:/LinkedinProjects/garda_ws/garda_ws/fpga/experiments/parallel8/tb_src_policy_core.sv:89) (baris 89–93).

```verilog
        for(i=0;i<A;i=i+1)begin
            {activation_accumulator,activation_output}=activation_inputs[i][40:0];#1;
            if({activation_saturated,activation_value}!==activation_expected[i][16:0])
                $fatal(1,"Activation case %0d mismatch: acc=%0d output=%0d",i,activation_accumulator,activation_output);
            checks=checks+1;
```
**8.364 activation cases lulus ulang** bersama 236 network vectors. UART juga memeriksa domain observasi: LiDAR [0,256], fitur lain [-256,256].

**Tidak ditemukan:** detector LiDAR/IMU spoofing, autentikasi sumber sensor, atau kampanye attack test dengan data palsu tetapi masih dalam domain yang sah. Nilai palsu seperti LiDAR jauh atau IMU stabil dapat lolos domain check. Clamp membatasi besar action, tidak menetapkan kebenaran sensor atau keselamatan gerak. Klaim aman: **bounded normalized output and invalid-domain rejection**, bukan “spoofing protection verified”.

### 15 — Serial frame replay → sequence numbers + HMAC next

**Tidak ditemukan sequence ID/nonce/HMAC pada frame neural UART saat ini.** Parser menerima header/opcode/length, payload 148 byte dan CRC; tidak ada counter freshness kriptografis:

Sumber: [fpga/rtl/garda_src_policy/garda_src_policy_uart.v:171](D:/LinkedinProjects/garda_ws/garda_ws/fpga/rtl/garda_src_policy/garda_src_policy_uart.v:171) (baris 171–180).

```verilog
                        152: begin
                            position<=0;
                            if (rx_data!=crc) reject(8'd6);
                            else if (invalid_observation) reject(8'd8);
                            else begin
                                if (accepted_frames!=32'hffffffff)
                                    accepted_frames<=accepted_frames+1'b1;
                                load_index<=0; mode<=LOAD;
                            end
                        end
```
Jangan keliru dengan sequence pada **map planner**:

Sumber: [fpga/rtl/garda_costmap_manager.v:24](D:/LinkedinProjects/garda_ws/garda_ws/fpga/rtl/garda_costmap_manager.v:24) (baris 24–25).

```verilog
   if(loading || frame_sequence<=committed_sequence || fault) begin fault<=1;loading<=0;end
   else begin loading<=1;count<=0;pending_sequence<=frame_sequence;end
```
Test map replay memang tersedia pada [fpga/verification/tb_safety_units.v:64](D:/LinkedinProjects/garda_ws/garda_ws/fpga/verification/tb_safety_units.v:64) dan lulus dalam suite units. Ini bukan perlindungan replay pada neural inference UART. Late-response fault latch di host juga bukan HMAC/sequence setiap request.

Slide memberi label **Next**; HMAC dan neural frame anti-replay tetap roadmap. Tidak diimplementasikan dalam audit ini.

### 16 — Weight tampering → weights in ROM, no write path

Pada salah satu lane Parallel8, bobot dimuat saat inisialisasi dan selanjutnya dibaca sinkron:

Sumber: [fpga/experiments/parallel8/garda_src_policy_core.v:108](D:/LinkedinProjects/garda_ws/garda_ws/fpga/experiments/parallel8/garda_src_policy_core.v:108) (baris 108–111).

```verilog
        initial $readmemh(BANK_FILE,memory);
        always @(posedge clk) data <= memory[address];
        assign weight[0] = data;
        assign product[0] = operand * weight[0];
```
Memory bobot tidak memiliki port write runtime; penulisan hidden activation dan accumulator adalah storage yang berbeda. Jadi deskripsi **no runtime weight-write port** didukung source.

Test bit-exact membandingkan output jaringan dengan oracle dan memeriksa seluruh 192 hidden activation pada tiap vector. **Lulus ulang untuk 236 vectors**. Artefak `simulation_acceptance.json` mencatat bank_words_verified=18.051; ini bukti struktur/model, bukan penetration test.

**Tidak ditemukan:** test serangan mengganti ROM/bitstream lalu membuktikan penolakan oleh hardware, authenticated model load, atau secure boot. ROM dalam FPGA tetap dapat berubah bila FPGA direconfigure. Gunakan istilah **runtime read-only weights**, bukan kebal semua weight tampering.

### 17 — Hacked host rewrites I/O → microcode locked while running

Write enable program memory dibatasi core state:

Sumber: [src/gardachip_top.v:38](D:/LinkedinProjects/garda_ws/garda_ws/src/gardachip_top.v:38) (baris 38–38).

```verilog
 wire memory_write = rst_n && host_write && host_address == 4 && !core_enabled;
```

Sumber: [src/gardachip_top.v:95](D:/LinkedinProjects/garda_ws/garda_ws/src/gardachip_top.v:95) (baris 95–97).

```verilog
    if (!core_enabled) byte_address <= byte_address + 1'b1;
    else errors[host_tid] <= 1;
   end
```
Test mencoba live write, memeriksa error, address tidak maju, dan program tidak berubah:

Sumber: [test/test_rtl.py:361](D:/LinkedinProjects/garda_ws/garda_ws/test/test_rtl.py:361) (baris 361–367).

```python
          // Live memory writes must be rejected without advancing the address.
          wr(5, 0); wr(2, 0); wr(3, 0); wr(4, 8'hEF);
          rd(1, value); if(!value[4]) $fatal(1,"missing write protection error");
          rd(2, value); if(value !== 0) $fatal(1,"rejected write advanced address");
          wr(0, 0); rd(4, value); if(value !== 8'h01) $fatal(1,"live memory changed");
          wr(11, 1); rd(1, value); if(value[4]) $fatal(1,"error clear");
          wr(9, 1); if(dut.output_oe_q !== 0) $fatal(1,"stop did not release pins");
```
**Lulus ulang.** Program-memory lock saat `core_enabled=1` sudah diimplementasikan pada ASIC protocol engine.

Namun host tetap bisa menulis control register yang mematikan core:

Sumber: [src/gardachip_top.v:100](D:/LinkedinProjects/garda_ws/garda_ws/src/gardachip_top.v:100) (baris 100–100).

```verilog
     0: core_enabled <= host_data[0];
```
Tidak ditemukan autentikasi/otorisasi host untuk jalur itu. Setelah core dimatikan, host sah menurut protokol dapat mengubah program dan konfigurasi. Jadi lock ini mencegah modifikasi tak konsisten ketika running; **bukan** perlindungan penuh terhadap hostile host, dan tidak mengunci semua register I/O. Label Next untuk mitigasi serangan penuh masih masuk akal.

### 18 — Tampered bitstream → hash manifest; encryption next

Manifest SHA-256 dan verifier file tersedia:

Sumber: [fpga/scripts/freeze_release.py:37](D:/LinkedinProjects/garda_ws/garda_ws/fpga/scripts/freeze_release.py:37) (baris 37–47).

```python
def check_mapping(mapping):
    problems = []
    for name, entry in mapping.items():
        path = local(name)
        expected = entry if isinstance(entry, str) else entry['sha256']
        if not path.is_file() or sha(path) != expected:
            problems.append(name)
    if problems:
        raise RuntimeError('Changed or missing recorded files: ' + ', '.join(problems[:12]))

def verify_build(name):
```
Source pembuatan manifest: [fpga/scripts/create_manifest.py:44](D:/LinkedinProjects/garda_ws/garda_ws/fpga/scripts/create_manifest.py:44). Daftar SOF SHA-256 juga dibuat pada `freeze_release.py`. Ini membuktikan tooling integritas file, bukan encryption.

Test [fpga/scripts/test_release_integrity.py:11](D:/LinkedinProjects/garda_ws/garda_ws/fpga/scripts/test_release_integrity.py:11) memeriksa helper hash/link-target dan perubahan bytes. **Bukan** test tampered SOF. Pemeriksaan release penuh tidak dijalankan dalam audit ini karena bukan syarat untuk membuktikan keberadaan helper dan ada perubahan lokal lama; dokumen ini tidak mengklaim semua manifest historis masih cocok.

**Tidak ditemukan:** gate-level/board test menolak bitstream yang telah dimodifikasi, signed bitstream verification dalam boot chain, key management, atau encrypted configuration yang aktif. SHA-256 tanpa trust anchor/signature tidak mencegah penyerang mengganti file sekaligus manifest. Status slide Next harus dipertahankan.

## 4. Test yang benar-benar dijalankan pada audit ini

Seluruh run di bawah menggunakan source existing, tanpa menambahkan test. Icarus Verilog 12.0 (devel) dan Python 3.11.9. Hasil simulator ditulis ke temporary directory terpisah agar artefak existing tidak ditimpa.

| Run | Hasil aktual | Yang dibuktikan |
|---|---|---|
| `run_safety_regression.py` dengan `OUT` sementara | **PASS: 111.210 oracle comparisons; 111 checkpoint** | Gate 12, units 31, top 29, UART 39; semua outcome 0–11. |
| `run_host_regression.py` dimuat sebagai unittest module | **29 tests PASS**, 0 failure/error | Fixture bridge/MCU/controller, domain, deadline, stale sensor, final envelope dan STOP request. |
| `run_lidar_regression.py` dimuat sebagai unittest module | **16 tests PASS**, 0 failure/error | Fixture driver/ROS/serial, frame parsing, acquisition freshness, malformed data. |
| Tujuh method existing `test/test_rtl.py` | **7 tests PASS**, 0 failure/error | Pin conflict, host write protection, I²C stretch/NACK, concurrency, UART framing/glitch. |
| Parallel8 `tb_src_policy_core.sv` | **PASS: 236 network vectors, 8.364 activation cases, 54.399 assertions** | Bit-exact inference, clamp/boundaries, core latency 6.916 cycles, abort/fault/reset. |
| Parallel8 `tb_board_wrapper.sv` | **18 checkpoints PASS** | KEY safety, zero residual, error latch, reset dan UART wrapper. |

Total **52 unittest cases** pada tiga kelompok fixture/protocol (29+16+7); angka tersebut terpisah dari 111.210 vektor gate dan assertion testbench. Jangan menjumlahkannya sebagai coverage seluruh 18 gangguan fisik.

Catatan reproduksi: percobaan wrapper pertama berhenti karena folder `artifacts/` belum dibuat dalam temporary directory audit. Folder kerja tersebut kemudian dilengkapi dan test existing diulang hingga 18 checkpoint PASS. Ini perbaikan setup audit sementara, tidak mengubah RTL atau testbench.

Tidak ada run fisik worker, liquid, EMI, blackout, wet-floor, battery brownout, sensor spoofing atau hostile-host penetration pada audit ini. Hasil GitHub Actions sebelumnya juga tidak dipakai sebagai PASS: job terblokir billing sebelum langkah test berjalan.

## 5. Klaim yang perlu ditandai belum selesai atau dipersempit

**Klaim berlabel verified/Sim/RTL yang belum mempunyai bukti sesuai kalimat lengkap:**

- Training lag **5–15 ms**: implementasi random lag dan bukti training terkait model belum ditemukan.
- Wet/oily floor + **wheel PID**: source slip tersedia, tetapi test lantai dan firmware/tuning PID tidak ditemukan; dt training sekitar 30,3 Hz, berbeda dari timer host 50 Hz.
- “FPGA zeroes motors”: neural wrapper menolkan residual; direct motor/PWM cutoff fisik tidak dibuktikan.
- “Forward capped **0,15 m/s**” sebagai RTL/global cap: yang ditemukan adalah residual scaling dan software envelope yang dapat naik sampai 0,60 m/s.
- LiDAR/IMU spoofing protection: yang diuji hanya domain dan clamp; spoof valid-domain belum ditangani/dibuktikan.
- Blackout, liquid-on-wiring, press-line EMI: baru stale-data/digital corruption proxy; test fisik sesuai judul belum ditemukan.
- Host OS jitter: fixed core execution tervalidasi, eksperimen jitter OS/end-to-end belum ditemukan.
- Weight tampering resistance: no runtime write port benar, tetapi serangan reconfiguration/model replacement tidak diuji.

**Next yang memang belum lengkap:** STM32 PWM cutoff 200 ms/brownout; OOD load shift; permanent I²C hang/recovery; neural UART sequence/HMAC; hostile-host authorization; encrypted/authenticated bitstream.

**Next yang mekanisme dasarnya justru sudah ada dan diuji:** pin-mask overlap rejection; running program write-lock; I²C finite clock-stretch/NACK dan concurrent contexts. Tetap jelaskan bahwa bukti tersebut milik ASIC protocol engine, bukan otomatis terintegrasi ke core neural FPGA.

Angka **111.210** pada slide valid sebagai jumlah pembandingan gate terhadap oracle. Ia **bukan jumlah uji untuk masing-masing 18 gangguan**, bukan physical test count, bukan gate/toggle coverage, bukan formal proof, dan tidak membuktikan seluruh chip/robot telah menerima semua serangan itu.

## 6. Sumber bukti dan identitas file

Link di atas menunjuk file lokal dan nomor baris checkout saat audit. Potongan kode disalin dari file yang ditemukan, bukan kode usulan. Berikut SHA-256 file yang dirujuk agar isi laporan bisa dicocokkan kembali:

| File | SHA-256 saat audit |
|---|---|
| `fpga/experiments/parallel8/garda_src_policy_core.v` | `0aff96cf9638582ab0bc6eabaf1462baa25a41196e1e73abc1aa4786cddc5d34` |
| `fpga/experiments/parallel8/tb_board_wrapper.sv` | `cf6afed010b93ce39a91f3337607298f02bf57853e5d3c66575d0ee5afa1543e` |
| `fpga/experiments/parallel8/tb_src_policy_core.sv` | `2548d3ed6b3173a973bb12335b90dcb41f86910b72dd5c754236977ee4ca8715` |
| `fpga/robot/jetauto/FPGA_VERILOG_TUTORIAL.md` | `7035404e4ff1cec47e8b4950a9b1b45193fc22ddb64e2c877c756800a59a3a97` |
| `fpga/rtl/garda_costmap_manager.v` | `5d58ee1bc90873f1c226ee0308c32fda351fdd97e23f8db6d7598c356fa58e94` |
| `fpga/rtl/garda_safety_security_gate.v` | `17e58e15e6e09e0e51e8e6d8a3731290931e607c7b607e1683d43c02e41f1ae6` |
| `fpga/rtl/garda_src_policy/garda_src_policy_uart.v` | `8c03e18a3a22afa550f387e74cb78c3b0d66df8a8efac1def37682e159e0e38a` |
| `fpga/scripts/create_manifest.py` | `080df0e7e4de11f2f62a135cb31189581e63edadd61a529514a7e43bc0506583` |
| `fpga/scripts/freeze_release.py` | `bb63de3da75874e34fc3fac752e9f59a30f81e6dc198b31d869645b012801b70` |
| `fpga/scripts/test_release_integrity.py` | `5febc247970db79400fd574765acc2eaa31acdef890cb38ad5b265c04f21a889` |
| `fpga/software_integration/src/garda_controller/garda_controller/controller_node.py` | `2ebe5e4e3ccefe93ae3a7242e42644d2b02bb1d3277bd6127b4b9875f77b758b` |
| `fpga/verification/run_host_regression.py` | `4c95d3956971b7db20125ee9eb20010163f437a2a27fec70d56c2b3e5a1ff53c` |
| `fpga/verification/tb_safety_top.v` | `4762ba74212f32ee4e3c235ecbeef8e9c1fac0cdfa2a60d1266aa9156f8b164d` |
| `fpga/verification/tb_safety_uart.v` | `4ed41b2180611c4cb770b12bdf4abaf26f48a9611a899d783f1992fd3a53dac9` |
| `fpga/verification/tb_safety_units.v` | `e3bff4dc16981efc860877ea798379fe3a2d08e06f57170a0db33438dc562ac5` |
| `src/garda_navigation/garda_navigation/retrain_ai.py` | `e3196b2cde0f54bb4c91a0ccf8bd638af58bae6810466b65234f7cb0380012c0` |
| `src/gardachip_top.v` | `ebbc52a887832c04a3b0c21bbe8161d75218906c2744f5183b03e4489aaefd41` |
| `test/test_rtl.py` | `f78b2f98f9e95900b04be0de2f153d098d72c5d191723dec2072db5ba69dab82` |

### Artefak existing dan pengikat arsitektur

- [fpga/experiments/parallel8/garda_src_policy.qsf](D:/LinkedinProjects/garda_ws/garda_ws/fpga/experiments/parallel8/garda_src_policy.qsf) — SHA-256 `9c94b0cd5779a8f1c55b2ca1b5f60607a7fdbdc87eff8ed9d01e2d56d930cef6`.
- [fpga/experiments/parallel8/garda_src_policy_de10_nano.v](D:/LinkedinProjects/garda_ws/garda_ws/fpga/experiments/parallel8/garda_src_policy_de10_nano.v) — SHA-256 `74238afb3675d3ebeea9d4290883197dd1dfce6402d18569fa7a5b4deea7ed81`.
- [fpga/evidence/current_safety/summary.json](D:/LinkedinProjects/garda_ws/garda_ws/fpga/evidence/current_safety/summary.json) — SHA-256 `6ee2c0ddcf35aeca485f4624f6504b018381847ac776fd9a353d6e9a0bf23aff`.
- [fpga/experiments/parallel8/artifacts/simulation_acceptance.json](D:/LinkedinProjects/garda_ws/garda_ws/fpga/experiments/parallel8/artifacts/simulation_acceptance.json) — SHA-256 `2f0912540a432872b3b11a7e427480fb35f68744f78651c736c0a2da5b61c8d8`.
- [fpga/verification/run_safety_regression.py](D:/LinkedinProjects/garda_ws/garda_ws/fpga/verification/run_safety_regression.py) — SHA-256 `86a7a6865b2392f8080ccd9441c77e67e2f17520540c1be13a7f287417547aa3`.

Artefak existing di atas mendukung penelusuran historis. Hasil rerun audit dijelaskan pada bagian 4; simulator rerun memakai folder sementara, sehingga tidak menimpa artefak tersebut.

Dokumen audit ini tidak mengesahkan sertifikasi keselamatan, keamanan, sign-off ASIC atau kesiapan gerak robot. Tidak ada implementasi gap yang ditambahkan atas permintaan audit ini.
