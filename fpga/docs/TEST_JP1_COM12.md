# Repeatable COM12 test on JP1 pins 1/2

Double-click **IGOR - Uji UART COM12 JP1 Pin 1-2** on the Windows Desktop.
Its target is `fpga/bitstreams/TEST_JP1_COM12.bat`.

From the adapter viewpoint: TX goes to JP1 pin 1 (FPGA RX/V12), RX goes to JP1
pin 2 (FPGA TX/E8), GND goes to JP1 pin 12, and VCC is disconnected. Disconnect
Jetson TX/RX from pins 1/2 before using this adapter. Use 3.3-V TTL signals.

The board must already run the original Parallel8 JP1 image at 921600 baud.
The test does not reprogram the board. Close MobaXterm/other apps on COM12,
release KEY1 and reset with KEY0 when needed.

The launcher sends ten known observation frames and checks the 11-byte response,
CRC and raw Q8.8 results `[-46,60,34]`. It prints received bytes and PASS/FAIL,
then keeps the window open. No STM or motor commands are sent.

Every run creates a new local `fpga/evidence/jp1_uart/<UTC timestamp>/` folder
containing settings, host output and transaction records. Captures are not
automatically uploaded. Programming success alone does not mean this test passes.

Optional PowerShell overrides:

```powershell
./fpga/scripts/test_jp1_com12.ps1 -Port COM12 -Iterations 1
```
