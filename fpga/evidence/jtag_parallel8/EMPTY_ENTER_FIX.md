# Empty Enter console fix

The user-reported log is preserved in `reported_empty_enter_issue.log`. Its first
inference passed, but subsequent reports had zero received bytes, unchanged
accepted count, and old response bytes still displayed. The console previously
treated any CR/LF as submission, even when no hexadecimal frame had been entered.
This made empty Enter wait for a nonexistent response and report FAIL. Error
`0B` separately records normal result expiry after the policy freshness limit;
the freshness limit is retained.

The corrected console submits a custom frame on newline only when hex input has
started. It ignores empty CR/LF, resets hex entry for `r`/`!`, and displays `--`
for byte positions absent from the current response. It does not relabel missing
responses as successes. The Parallel8 arithmetic, weights, UART frame validation,
CRC rejection and safety timeout logic are unchanged.

The added simulation reproduces repeated empty CR/LF, custom-frame CR+LF, and
`r` plus CR+LF, waiting longer than the reply timeout to ensure no extra report.
It also checks actual-core results, bad CRC and E-stop inhibition.

Quartus full compile completed at **19:39:07 WIB**, 19 October 2026, with zero
errors and 53 warnings. The corrected image was programmed to the physical board
at **19:39:32 WIB**, with zero programming errors/warnings. See
`20261019T123946Z/programming.log` and the project build reports.

All **10 physical checks passed** in `20261019T123946Z/physical_commands.json`:
three real inferencing requests (`r`, `r`+CR, `r`+CR+LF), three checks for no extra
reports, twenty ignored blank CR+LF pairs, malformed-CRC rejection, a full hex
frame, and a check that its CR+LF produced one report. Each valid request returned
the same 11 bytes and **6,916 cycles / 138.32 µs**.

Corrected SOF SHA256:
`268149fbd1eb9bd2102c5a4b6dfc7ae4f13e60101ead04a1d9aaa10788ed9019`.
The Desktop shortcut uses this image through the updated hash receipt.
