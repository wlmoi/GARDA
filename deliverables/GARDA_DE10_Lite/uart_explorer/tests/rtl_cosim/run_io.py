"""RTL co-sim of the physical inputs: what each DE10 switch / key does, read back over UART (ops 7, 14, 16)."""
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]; sys.path.insert(0, str(ROOT))
import protocol as P
Q = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\msys64\ucrt64\bin"); RTL = ROOT.parents[2] / "dashboard/dist/source/rtl"
reqs = [(7, 0), (14, 0), (16, 0)]; frames = [P.encode_request(o, p) for o, p in reqs]
# name, SW[3:0], KEY[1:0], expected fault_code (5 = idle, no map committed)
SCEN = [("idle", 0b0000, 0b11, 5), ("SW0 on (unused by garda_uart_top)", 0b0001, 0b11, 5), ("SW1 on (unused)", 0b0010, 0b11, 5),
        ("SW2 on (ready inhibit)", 0b0100, 0b11, 4), ("SW3 on (protective stop)", 0b1000, 0b11, 3),
        ("KEY1 held (E-stop)", 0b0000, 0b01, 2), ("SW3 + KEY1 (priority)", 0b1000, 0b01, 2)]
fails = 0
for name, sw, key, want in SCEN:
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); (td / "sim").mkdir(); (td / "assets/neural_24_64_64_4").mkdir(parents=True)
        shutil.copy(ROOT / "data/bram_unified_weights_padded.mem", td / "assets/neural_24_64_64_4/")
        for v in RTL.glob("*.v"): shutil.copy(v, td / "sim")
        shutil.copy(HERE / "tb.v", td / "sim"); (td / "sim/frames.hex").write_text("\n".join(f"{b:02x}" for f in frames for b in f))
        env = dict(os.environ); env["PATH"] = str(Q) + ";" + env["PATH"]
        subprocess.run([str(Q / "iverilog.exe"), "-g2012", f"-DNFRAMES={len(frames)}", "-DNN_WAIT_AT=99", f"-DSWV=4'b{sw:04b}", f"-DKEYV=2'b{key:02b}", "-o", "s.vvp"] + [str(p) for p in (td / "sim").glob("*.v")], cwd=td / "sim", env=env, check=True)
        out = subprocess.run([str(Q / "vvp.exe"), "s.vvp"], cwd=td / "sim", env=env, capture_output=True, text=True, timeout=600).stdout
    per, cur = {}, None
    for ln in out.splitlines():
        m = re.match(r"(FRAME (\d+)|RX ([0-9a-f]{2}))", ln.strip())
        if m and m.group(2) is not None: cur = int(m.group(2)); per[cur] = bytearray()
        elif m: per[cur].append(int(m.group(3), 16))
    s, g, l = (P.decode_response(bytes(per[i]), expect_op=reqs[i][0]) for i in range(3))
    ok = all(x["valid"] for x in (s, g, l)) and s["fields"]["fault_code"] == want and not s["fields"]["enable"] and g["fields"] == {"v_command": 0, "omega_command": 0}
    fails += not ok
    print(("PASS " if ok else "FAIL ") + f"{name}: fault_code={s['fields']['fault_code']} (want {want}) enable={s['fields']['enable']} v/w={g['fields']}")
print("RESULT:", "ALL PASS" if not fails else f"{fails} FAILED"); sys.exit(bool(fails))
