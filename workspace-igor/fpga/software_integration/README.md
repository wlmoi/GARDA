# Software integrasi di dalam paket FPGA

Folder ini adalah workspace ROS 2 yang memuat salinan software referensi beserta
perbaikan integrasi hardware. Source asli `igor_ws/src` tetap menjadi referensi.
Model neural tetap **74 → 128 → 64 → 3**, sesuai RTL source-policy. Tidak ada
pelatihan ulang atau penggantian bobot pada penyiapan ini.

Pada Jetson dengan ROS 2 Humble, NumPy, pyserial dan dependensi paket terpasang:

```bash
cd igor_ws/fpga/software_integration
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
ros2 launch igor_bringup bringup.launch.py algorithm:=cl_drl_cbf use_fpga:=true fpga_port:=/dev/fpga fpga_baudrate:=921600
```

Command tersebut memakai bitstream **source_policy**, bukan planner legacy.
Mode FPGA mendukung `cl_drl` dan `cl_drl_cbf`. Kombinasi FPGA dengan
`cl_drl_dwa` ditolak karena mini-DWA belum menerima residual hardware secara
langsung. DWA/APF dan mini-DWA CPU dapat dijalankan dengan `use_fpga:=false`.

Simulasi serial harus dipilih dengan `use_mock_serial:=true`. Mode hardware
menolak FPGA, MCU, atau LiDAR yang tidak tersedia; tidak ada fallback otomatis
ke data sensor buatan. Bukti fixture software tersedia pada
`../evidence/current_host/` dan `../evidence/current_lidar/`; belum ada eksekusi
ROS end-to-end pada Jetson atau robot fisik dalam sesi ini.

Perbaikan keselamatan yang diterapkan:

- Bridge memvalidasi shape, domain, header, length, CRC dan rentang residual.
  Total exchange memiliki deadline monotonic 20 ms. Kegagalan transport ditahan
  sampai FPGA direset dan bridge direstart, karena protokol belum punya ID transaksi.
- Controller menolkan **seluruh empat RPS**, bukan sekadar residual, bila
  transport, sensor atau perintah gagal. Perintah/scan/IMU usang, timestamp masa
  depan dan nilai nonfinite ditolak. Lease diperiksa lagi setelah komputasi.
- Hard-stop jarak ≤0,22 m, batas kecepatan/envelope, dan perintah operator nol
  berlaku setelah seluruh cabang inferensi. Filter CBF menerima titik sensor;
  hasil filter tidak dapat melewati batas akhir controller.
- MCU tidak otomatis memakai mock, memeriksa short write dan mengekspos apakah
  transmisi STOP terkonfirmasi. Putusnya kabel MCU tidak membuktikan motor
  menerima STOP; watchdog/interlock motor fisik harus diuji terpisah.
- Driver LiDAR hanya menerbitkan satu pesan per revolusi lengkap yang baru.
  Data lama tidak diberi timestamp baru. Coverage minimal 180 bin, umur maksimal
  0,25 s, dan bin yang tidak diketahui diisi jarak konservatif 0,15 m.
  [LIDAR_SAFETY.md](LIDAR_SAFETY.md) menjelaskan parser dan batas perangkatnya.

Balasan residual yang sudah lengkap diterima host sebelum tombol E-stop ditekan
tidak bisa ditarik kembali. KEY1 menghambat jalur FPGA dan transaksi berikutnya,
tetapi STOP motor segera memerlukan interlock fisik independen atau integrasi
langsung keluaran gerbang motor. Jalur policy tidak menerima peta; klaim kurir
tanpa keputusan dan AI → motion checker → gate → motor tetap butir integrasi
terbuka pada checklist.
