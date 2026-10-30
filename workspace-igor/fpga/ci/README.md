# GitHub Actions dan pemeriksaan lokal

Semua file yang disiapkan pada pekerjaan ini berada di `fpga`. GitHub hanya
menemukan workflow dalam **`.github/workflows/` pada root repository**; file
di `fpga/ci/workflows/` adalah paket siap dipasang dan belum menjadi workflow
aktif karena lokasinya. Pembatasan perubahan hanya di `fpga` dipertahankan.
Lokasi tersebut mengikuti [aturan workflow resmi GitHub](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#about-yaml-syntax-for-workflows).

## Memasang pada repository `igor_ws`

Repository harus menyertakan `fpga/` **dan** `src/` pada commit yang sama.
Uji provenance policy membaca bobot asli dari `src/` sebagai referensi baca
saja; tidak mengubahnya. Paket ini tidak ditujukan sebagai repository
standalone `fpga` karena referensi tersebut diperlukan.

Pengguna atau maintainer memasang dua file berikut dengan menyalinnya ke
`.github/workflows/` pada root repository, lalu meninjau dan commit perubahan:

| Sumber dalam paket | Tujuan pada root repository |
|---|---|
| `ci/workflows/rtl-verification.yml` | `.github/workflows/rtl-verification.yml` |
| `ci/workflows/quartus-src-policy.yml` | `.github/workflows/quartus-src-policy.yml` |

Jika tujuan sudah ada, bandingkan dahulu dan terapkan versi paket yang sudah
ditinjau. Penyalinan tersebut merupakan langkah instalasi di luar `fpga`;
pekerjaan ini hanya menyiapkan paketnya. Tidak ada klaim bahwa run GitHub
Actions remote telah dijalankan.

## Isi workflow

`rtl-verification.yml` berjalan pada push, pull request, dan workflow dispatch,
dengan izin repository `contents: read`. Empat job Ubuntu 24.04 terpisah:

| Job | Pemeriksaan yang dijalankan | Bukti yang diunggah |
|---|---|---|
| `src-policy` | Check ROM terhadap source, integer oracle, core, UART, lalu wrapper DE10-Nano aktual | Vektor, hasil, compile/simulation log, VCD, GTKWave, checkpoint wrapper |
| `safety` | Gate, kontrol, peta, urutan upload, logger, deadline/freshness, E-stop dan UART rusak | `evidence/current_safety/` |
| `host` | Bridge fail-closed, STOP controller, MCU, driver LiDAR dan 10 uji integritas capture UART dengan serial fixture | `evidence/current_host/`, `evidence/current_lidar/`, `evidence/current_checks/` |
| `legacy` | Cocotb neural/planner/TinyTapeout, netlist generic, integritas link, serializer motor, lease/arm STOP dan decoder independen | XML, JSON coverage, offline motor log dan byte UART |

Simulator diinstal sebagai `iverilog` dari Ubuntu. Python 3.11 dan dependensi
Python dipin pada file workflow; cocotb memakai `requirements.txt`. Legacy
suite merupakan pemeriksaan tambahan untuk arsitektur lama 24-64-64-4 dan
planner; hasilnya tidak menggantikan policy source 74-128-64-3.

Artifact disimpan juga saat job gagal (`if: always()`), dengan nama unik
berbasis commit dan masa simpan 30 hari. Bukti aktual harus dibaca bersama
status run dan log; artifact lama yang ada di repository bukan hasil run baru.

`quartus-src-policy.yml` hanya menggunakan **workflow dispatch manual** pada
runner tepercaya dengan label `self-hosted`, `Windows`, `X64`, `quartus-25`.
Runner memerlukan PowerShell 7 (`pwsh`), Git, Quartus Prime Standard 25.1,
device support Cyclone V, dan lisensi yang valid. Tentukan `QUARTUS_SH`
(path lengkap `quartus_sh.exe`), atau `QUARTUS_ROOTDIR`, atau tambahkan
`quartus_sh.exe` ke PATH. Job menjalankan
`python scripts/build_quartus.py source_policy --quartus-sh <path>` untuk
memeriksa versi, mencatat SHA input sebelum/sesudah compile, melakukan flow
fitter/assembler/timing, memeriksa seluruh slack nonnegatif dan 13 pin
top-level, serta menyimpan output, SHA SOF/report dan receipt
`evidence/current_builds/source_policy.json`. Workflow ini tidak memprogram perangkat
atau mengirim perintah motor. Self-hosted runner tidak menerima event PR.
Gunakan Actions Runner versi 2.327.1 atau lebih baru untuk runtime Node 24
yang dipakai [checkout v6](https://github.com/actions/checkout/blob/d23441a48e516b6c34aea4fa41551a30e30af803/README.md).
Job manual ini membangun policy source saja. Receipt tersebut tidak
menggantikan acceptance seluruh paket yang juga memerlukan build planner
dan semua simulasi baru; jangan menjalankan freeze seluruh rilis hanya
berdasarkan job ini.

## Menjalankan pemeriksaan yang sama secara lokal

Dari folder `fpga`, dengan Python 3.11 dan Icarus Verilog pada PATH:

```powershell
python -m pip install -r requirements.txt numpy==2.2.6 pyserial==3.5
python scripts/run_all_checks.py
```

Perintah tersebut menjalankan seluruh pemeriksaan simulasi/host secara
berurutan dan berhenti jika sebuah langkah gagal. Ia **tidak** menjalankan
Quartus, memprogram board, membuka serial fisik, atau menggerakkan motor.
Semua log baru dan report status berada di
`evidence/current_checks/`; suite masing-masing juga menulis bukti rinci
ke direktori evidence-nya. Report mencantumkan command, working directory,
exit code, waktu, SHA log dan SHA runner. Simpan direktori tersebut bersama
hasil suite yang dipakai dalam review.

Pilihan yang lebih kecil:

```powershell
python scripts/run_all_checks.py --suite policy
python scripts/run_all_checks.py --suite safety
python scripts/run_all_checks.py --suite host
python scripts/run_all_checks.py --suite legacy --suite motors
python scripts/run_all_checks.py --list
```

Perintah individual yang dipakai workflow:

```powershell
python verification/src_policy/run.py --check
python verification/run_board_wrapper.py
python verification/run_safety_regression.py
python verification/run_host_regression.py
python verification/run_lidar_regression.py
python verification/test_capture_hardware_safety.py
python verification/run.py all
python verification/run.py tt_generic
python scripts/test_release_integrity.py
```

Uji motor lengkap dapat dijalankan dengan `--suite motors`; ia mengompilasi
dan menjalankan dua testbench serta dua decoder offline. Dependensi yang
hilang menyebabkan FAIL, bukan skip diam-diam. Bukti physical E-stop/output
dan log FPGA tetap memerlukan uji hardware terpisah sebagaimana dijelaskan
di [panduan programming](../docs/FPGA_PROGRAMMING.md).

Waveform rilis dikemas sebagai `.vcd.gz`. Setelah clone, pulihkan dahulu
sebelum membuka save file GTKWave:

```powershell
python scripts/unpack_current_waveforms.py
gtkwave evidence/current_safety/top.vcd evidence/current_safety/top.gtkw
```

Script unpack hanya menulis `.vcd` pada folder bukti di dalam `fpga`.
Run CI yang baru menghasilkan waveform `.vcd` langsung dari simulator.
