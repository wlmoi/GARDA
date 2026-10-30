# DE10-Nano: pilih project yang sesuai

Seluruh paket `fpga` harus dipertahankan, karena kedua QSF membaca source
kanonik `../../rtl`. Folder `rtl` salinan board adalah referensi kompatibilitas;
source build aktual berada di `fpga/rtl`.

| Profil | Project | Top | Host UART |
|---|---|---|---|
| PPO dari software 74-128-64-3 | [src_policy/igor_src_policy.qpf](src_policy/igor_src_policy.qpf) | igor_src_policy_de10_nano | 921600, request 153/respons 11 byte, CRC8 Maxim |
| Planner peta + gate + neural legacy 24-64-64-4 | [quartus/igor.qpf](quartus/igor.qpf) | igor_uart_top | 115200, frame 8 byte, CRC8 0x07 |

Kedua profil memakai 5CSEBA6U23I7 dan clock 50 MHz. Pin planning dan SDC
sudah disertakan. Buka QPF, lalu Assignments > Pin Planner untuk melihat
lokasi dan standar I/O. UART fabric berada di JP1 pin 1 RX, pin 2 TX dan
pin 12/30 GND, menggunakan TTL 3,3 V. KEY0 reset; KEY1 E-stop demo.

Planner LED0=gate enable, LED1=reset dilepas, LED2=busy, LED3=done,
LED 7:4=fault. SW2 ready inhibit dan SW3 protective stop; SW 0/1 tidak dipakai.
Arti LED policy berbeda; lihat [README policy](src_policy/README.md).

Hasil terbaru, warnings dan hash:
[BUILD_STATUS.md](../BUILD_STATUS.md),
[receipt planner](../evidence/current_builds/planner.json),
[receipt policy](../evidence/current_builds/source_policy.json),
[release manifest](../evidence/current_release/manifest.json).
Programming: [BOARD_PROGRAMMING.md](../docs/BOARD_PROGRAMMING.md).

Host legacy [igor_uart.py](host/igor_uart.py) menyediakan status, ROM readback,
100-vector neural check dan DWA demo. RESET KEY0 sebelum setiap scene. Map
freshness dan command lease 20 ms harus diperhitungkan. Transport motor memiliki
protokol terpisah; SOF planner ini belum langsung menserialkan pesan motor.
