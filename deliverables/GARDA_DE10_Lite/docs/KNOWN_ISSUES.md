# Known issues and limitations

1. **Timing closure is part of every build report.** `scripts/build.py` marks a
   bitstream `release: true` only when setup, hold, recovery and removal slack are
   non-negative at all three corners (Slow 85 °C, Slow 0 °C, Fast 0 °C). Otherwise the
   file is named `garda_de10_lite_TIMING_NOT_MET.sof`. The critical path is legacy
   GARDA logic: rollout tile `best_score` → 4-way candidate selector → UART response
   snapshot. It has about 0 ns of margin at 50 MHz on MAX 10 C7 silicon. See
   `reports/VERIFICATION_REPORT.md` for the exact slack of the delivered file.
2. **The bring-up bitstream** `output/garda_de10_lite_bringup_slack-0.186.sof` (no VGA)
   misses setup timing by 0.186 ns at the Slow 85 °C corner only. It was programmed once
   for bring-up. Do not use it for demonstrations once a release build exists.
3. **Planner demo is one-shot and slow over UART.** A planner run needs a full
   16 384-cell map. The protocol uses one 8-byte request/response per cell, so the upload
   takes tens of seconds at 115200 baud. Map freshness and the command lease expire 20 ms
   after commit/run (original GARDA safety parameters, not changed), so each run needs a
   fresh upload. The E-stop test is armed in hardware (`ESTOP_TEST`) so that the
   intervention measurement does not depend on USB latency.
4. **921600 baud** is supported by the RTL parameter (`build.py --baud 921600`, divisor 49 at
   45 MHz, −0.35 % error). It is not used in the delivered build and has not been tested on hardware.
5. **Clone PL2303 adapters** are refused by the current Windows Prolific driver. Use
   `START_CONTROL_CENTER_WSL.bat` (usbipd + Linux driver) or a genuine FTDI/CP210x/CH340 adapter.
6. **`.pof` (internal flash) programming is not offered.** The build produces a `.pof`
   (configuration mode "Single image with ERAM", needed for the neural-weight ROM
   initialisation). The Control Center only does volatile JTAG `.sof` configuration.
   Flash programming has not been validated and stays a manual Quartus Programmer step.
7. **No motors are driven.** The FPGA outputs the safety-gated (v, ω) command and
   motor_enable only as status. This build has no motor-driver pins.
8. **Neural core and planner are separate datapaths**, as in the original GARDA FPGA
   design. The neural network (24-64-64-4, Q8.8) runs on UART-supplied inputs. It does not
   feed the DWA planner.
9. **The VGA screen is observation only.** It shows values one clock (20 ns) after the
   safety gate computes them. Its own reset comes from KEY0 only.
10. **Watchdog and host E-stop latch until reset**, the same as the existing GARDA E-stop
    (garda_top FAULT state is sticky). Recovery is KEY0 or `SAFE_RESET`. `SAFE_RESET` is
    refused while KEY1 is held.
11. **Core clock is 45 MHz, not 50 MHz.** The unmodified GARDA core misses 50 MHz on MAX 10 C7
    silicon by about 0.44 ns at 85 °C. The PLL runs it at 45 MHz. All real-time constants (20 ms
    lease and freshness, 100 ms UART gap, watchdog ms, baud) are rescaled so they keep their
    original meaning. Planner and neural cycle counts are unchanged; wall-clock latency is about 11 % longer.
12. **Two hosts share one protocol engine.** A frame from one port while the other owns the link
    is dropped (collision, counted in PORT_INFO). That host gets no reply and must retry, which
    `garda_link.py` does automatically for read-only commands and the E-stop. During a long laptop map
    upload, the Jetson only gets the link in the gaps between frames. The physical E-stop is KEY1.
