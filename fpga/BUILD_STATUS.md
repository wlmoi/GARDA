# Status build dan handoff DE10-Nano

Dihasilkan dari receipt kompilasi dengan input tidak berubah. Target kedua project: **5CSEBA6U23I7, Quartus Prime Standard 25.1, clock 50 MHz**.

| Project | ALM | Register | M10K | DSP | Setup terburuk | Hold terburuk | Pin | Warning |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| source_policy | 3,249 | 5996 | 64 | 1 | +6.019 ns | +0.116 ns | 13 | 3 |
| planner | 5,048 | 1650 | 131 | 10 | +0.641 ns | +0.094 ns | 17 | 9 |

Seluruh corner setup/hold/recovery/removal/minimum-pulse-width yang dilaporkan nonnegatif. Pin locations, standar I/O 3,3 V, output drive 16 mA dan slew 1 tercantum eksplisit pada pinplan; laporan fitted `.pin` dan I/O memuat hasil penempatan aktual.

## Identitas build

- **source_policy** selesai 2026-10-17 08:22:09 WIB; receipt [JSON](evidence/current_builds/source_policy.json).
  SOF SHA256: `fb9fcd28136b647492d2284fef82beca34b97f8300ce0579c25e0745fa88cf4a`.
- **planner** selesai 2026-10-16 18:01:03 WIB; receipt [JSON](evidence/current_builds/planner.json).
  SOF SHA256: `84295ae937ab4a759efa1e4d21ebda09805559038bc4fef971894a8946d701d2`.

## Warning yang direview

Tiga warning policy berasal dari port tulis internal ROM (`data_a`, `waddr_a`, `we_a`) yang tidak memiliki driver karena memori digunakan read-only. Model parameter diinisialisasi dari MEM, dibandingkan dengan source, dan diuji melalui oracle integer. Ini bukan warning bahwa bobot aktif tidak terisi.

Planner juga mencatat RAM read-during-write pass-through logic dan dua input SW0/SW1 yang tidak mempengaruhi output. Referensi lengkap adalah warning pada `compile_current.log` dan `igor.map.rpt`. Tidak ada warning missing drive/slew sesudah pinplan eksplisit. Tidak ada critical warning atau timing gagal pada flow kompilasi rilis yang diterima. Pernyataan ini tidak mencakup Power Analyzer; analisis power terpisah mempunyai Critical Warning HPS dan confidence Low yang dijelaskan pada [METRICS_AND_POWER.md](docs/METRICS_AND_POWER.md).

## Pemeriksaan paket

```powershell
python scripts/freeze_release.py --check
```

Manifest [current_release/manifest.json](evidence/current_release/manifest.json) mengikat source, pinplan, model, hasil pengujian, laporan dan kedua SOF. Handoff image dan checksum ada di [bitstreams/](bitstreams/). Ubah source, bobot, QSF/SDC/pinplan berarti receipt lama tidak berlaku dan harus dibangun ulang.

## Status perangkat fisik

Status konfigurasi fisik terbaru dicatat per percobaan pada [evidence/current_programming/](evidence/current_programming/), dengan project, SHA256 SOF, chain, log Quartus dan field `hardware_programmed`. Programming SRAM yang sukses tidak otomatis membuktikan fungsi UART, motor/robot, daya atau latensi fisik. Lihat [BOARD_PROGRAMMING.md](docs/BOARD_PROGRAMMING.md), [GPIO_AND_HPS.md](docs/GPIO_AND_HPS.md), dan [FINAL_ACCEPTANCE.md](docs/FINAL_ACCEPTANCE.md) untuk prosedur dan pekerjaan tersisa.
