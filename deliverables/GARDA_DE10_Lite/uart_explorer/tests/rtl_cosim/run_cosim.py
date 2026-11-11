"""Co-simulate the real garda_uart_top RTL with Icarus Verilog against protocol.py.
usage: python tests/rtl_cosim/run_cosim.py [dir-with-iverilog.exe]"""
import re, shutil, subprocess, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]; sys.path.insert(0, str(ROOT))
import protocol as P, explorer as X
Q = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\msys64\ucrt64\bin")  # Icarus Verilog: pacman -S mingw-w64-ucrt-x86_64-iverilog
RTL = ROOT.parents[2] / "dashboard/dist/source/rtl"
vec = X.load_vectors()[0]; rom = X.read_mem(ROOT / "data/bram_unified_weights.mem")
reqs = [(7, 0), (8, 0), (8, 6019), (9, 0), (14, 0), (15, 0), (16, 0)]
reqs += [(10, i | ((x & 0xFFFF) << 8)) for i, x in enumerate(vec["inputs"])] + [(11, 0)]
nn_wait_at = len(reqs) - 1
reqs += [(12, 0)] + [(12, i) for i in range(4)] + [(13, 0)]
frames = [P.encode_request(o, p) for o, p in reqs]
bad = bytearray(P.encode_request(7, 0)); bad[6] ^= 0x55
frames += [bytes(bad), P.encode_request(7, 0)]       # malformed -> no reply; then sticky fault -> no reply
with tempfile.TemporaryDirectory() as td:
    td = Path(td); (td / "sim").mkdir(); (td / "assets/neural_24_64_64_4").mkdir(parents=True)
    shutil.copy(ROOT / "data/bram_unified_weights_padded.mem", td / "assets/neural_24_64_64_4/")
    for v in RTL.glob("*.v"): shutil.copy(v, td / "sim")
    shutil.copy(HERE / "tb.v", td / "sim")
    (td / "sim/frames.hex").write_text("\n".join(f"{b:02x}" for fr in frames for b in fr))
    import os; env = dict(os.environ); env["PATH"] = str(Q) + ";" + env["PATH"]
    srcs = [str(p) for p in (td / "sim").glob("*.v")]
    r = subprocess.run([str(Q / "iverilog.exe"), "-g2012", f"-DNFRAMES={len(frames)}", f"-DNN_WAIT_AT={nn_wait_at}", "-o", "sim.vvp"] + srcs, cwd=td / "sim", env=env, capture_output=True, text=True)
    if r.returncode: print(r.stdout, r.stderr); sys.exit("iverilog failed")
    r = subprocess.run([str(Q / "vvp.exe"), "sim.vvp"], cwd=td / "sim", env=env, capture_output=True, text=True, timeout=1500)
    out = r.stdout
if "DONE" not in out: print(out[-2000:], r.stderr[-1000:]); sys.exit("simulation did not finish")
per = {}; cur = None
for ln in out.splitlines():
    m = re.match(r"# (FRAME (\d+)|RX ([0-9a-f]{2}))", ln.strip()) or re.match(r"(FRAME (\d+)|RX ([0-9a-f]{2}))", ln.strip())
    if not m: continue
    if m.group(2) is not None: cur = int(m.group(2)); per[cur] = bytearray()
    else: per[cur].append(int(m.group(3), 16))
fails = 0
def chk(name, ok, extra=""):
    global fails; fails += not ok; print(("PASS " if ok else "FAIL ") + name, extra)
for i, (o, p) in enumerate(reqs):
    d = P.decode_response(bytes(per[i]), expect_op=o)
    chk(f"op {o} payload 0x{p:x}: valid 8-byte response, CRC ok, opcode echo", d["valid"], f"raw={bytes(per[i]).hex(' ')}")
    if o == 8: chk("  ROM word matches .mem", d["fields"]["rom_word"] == rom[p], f"{d['fields']['rom_word']:04x}")
n = len(reqs) - 6    # op12 poll index
chk("NN outputs match reference vector 0", [P.decode_response(bytes(per[n + 1 + k]))["fields"]["result_q8_8"] for k in range(4)] == vec["expected"], str(vec["expected"]))
chk("NN done flag set", P.decode_response(bytes(per[n]))["fields"]["done"])
print("NN latency cycles (RTL):", P.decode_response(bytes(per[len(reqs) - 1]))["data"])
chk("bad-CRC frame gets no response", len(per[len(reqs)]) == 0)
chk("next frame after fault gets no response (sticky)", len(per[len(reqs) + 1]) == 0)
print("RESULT:", "ALL PASS" if not fails else f"{fails} FAILED"); sys.exit(bool(fails))
