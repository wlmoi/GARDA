# Parallel8 USB-Blaster console variant

Open `igor_jtag.qpf` in Quartus 25.1 Standard. Target: DE10-Nano,
Cyclone V `5CSEBA6U23I7`, 50 MHz. All project changes reside under `fpga/`.
The accepted Parallel8 image and project are separate.

## One-click use

Double-click **IGOR - JTAG Terminal** on the Windows Desktop. The launcher checks
the installed SOF hash, programs the JTAG console image through USB-Blaster, and
opens the actual Quartus `nios2-terminal`. No COM port, HPS Linux, Nios CPU,
USB-to-TTL adapter, or MobaXterm session is needed for this variant.
Only one terminal should own the JTAG UART instance at a time.

Keep KEY1 released. KEY0 resets the design and clears the E-stop latch. FPGA SRAM
configuration is volatile; running the shortcut again restores the image after
board power-off. This does not program nonvolatile configuration flash.

The first known-vector inference starts about three seconds after reset:

```text
IGOR Parallel8 JTAG | r=demo !=badCRC | hex+Enter=frame
RX count=0xB FPGA bytes: 5A A5 02 06 D2 FF 3C 00 22 00 61
cycles=0x00001B04 accepted=0x00000001 rejected=0x00000000 error=0x00 CHECK=PASS
>
```

Type `r` to repeat. Type `!` to inject a frame with a deliberately wrong CRC:
the reply count must be zero, rejected count increases, error becomes `06`, and
`CHECK=PASS` means the rejection test passed. Missing byte slots display `--`;
they are not received zero-valued bytes or data retained from an earlier reply.
An E-stop during a normal demo yields `CHECK=FAIL`, error `01`, and no inference
reply. This is expected inhibition, not an instruction to bypass the stop.
`error` records the latest fault and may remain `06` after a later valid request.

For custom observations, paste a complete 153-byte frame as hexadecimal pairs
separated by spaces and press Enter. `CHECK=DATA` identifies a custom transaction;
it does not compare arbitrary observations against the built-in demo oracle.
Use only hex digits/spaces, then one Enter. Input is serviced while idle; wait
for the next `>` prompt before sending another transaction. Bare Enter, LF and
CR+LF without hexadecimal input are ignored. `r`, `r` followed by Enter, and a
custom frame followed by CR+LF each produce one report. A newline submits a
custom frame only after at least one hexadecimal digit has been entered.
The exact example request is in `source_manifest.json` (`demo_request_hex`).

## Actual signal path

```text
USB-Blaster JTAG
  ↕ Intel JTAG UART IP, instance 0 (64-byte FIFOs)
Avalon polling bridge (checks WSPACE, reads RVALID)
  ↕ ASCII console: r / ! / hexadecimal frame
UART serializer at 50 MHz / 54 clocks per bit
  → unchanged source policy UART receiver / CRC / input-domain checks
  → unchanged Parallel8 neural core, eight banks of original weights
  → unchanged policy UART transmitter
  → UART monitor → actual response bytes → ASCII JTAG report
```

UART TX remains on JP1 pin 2 for an optional external logic analyzer. Physical
JP1 RX is disconnected in this variant because the internal JTAG-fed serializer
owns the receiver. Use the original Parallel8 SOF for the physical JP1 UART link.
This is an inference console: it does not drive a motor or implement Ethernet.

The demo input is 64 LiDAR values of 205 and ten zeros, signed Q8.8. The expected
residual is `[-46, 60, 34]`, not motor commands. The report captures bytes decoded
from the running UART transmitter; the expected byte array is used only for
comparison. Core latency must be 6,916 cycles = 138.32 µs at 50 MHz. Host/JTAG
latency and the two serial stages are additional to that core latency.

## Build and verification

Run `python fpga/scripts/build_jtag_variant.py` from the repository root **before**
starting compilation. It copies the accepted core/banks, prepares pin constraints,
generates demo vectors/status formatting, and records source identity. Do not
regenerate sources or settings during a Quartus build.

From this project directory:

```powershell
iverilog -g2012 -I . -s tb_jtag_bytes -o bytes_test.vvp tb_jtag_bytes.v igor_jtag_console.v
vvp bytes_test.vvp | Tee-Object bytes_simulation.log
iverilog -g2012 -I . -s tb_jtag_console -o console_test.vvp tb_jtag_console.v igor_jtag_console.v igor_src_policy_core.v ../../rtl/igor_src_policy/igor_src_policy_uart.v ../../rtl/igor_uart_rx.v ../../rtl/igor_uart_tx.v
vvp console_test.vvp | Tee-Object console_simulation.log
& D:/Quartus-Program/quartus/bin64/quartus_sh.exe --flow compile igor_jtag
```

Then run `fpga/scripts/install_jtag_variant.ps1`. It requires successful full
compilation, nonnegative timing summary slack, the two passing simulation logs,
and an unchanged core source hash before installing the distinct SOF/receipt.
`output_files/igor_jtag.*.rpt` and `.summary` are the original Quartus reports.
Simulations cover byte order/backpressure, real neural inference, CRC rejection,
custom hex input, blank-line rejection, CR/LF command termination and E-stop;
they do not constitute exhaustive formal verification.

Vendor IP sources are referenced from the local Quartus installation and retain
their Altera licensing terms. Adjust the three absolute IP paths in the QSF when
using a different Quartus installation. The register protocol follows the
[Intel Embedded Peripherals IP User Guide](https://www.intel.com/programmable/technical-pdfs/683130.pdf).
