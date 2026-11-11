// Logical UART waveform reconstruction (8N1, LSB first). DECODED RECONSTRUCTION only: built from packet bytes,
// never from measured edges. Pure functions, shared by the browser and by tests/test_wave.js.
(function (root) {
  function frameBits(byte, parity) {
    const bits = [0];                                   // start bit (line low)
    let ones = 0;
    for (let i = 0; i < 8; i++) { const b = (byte >> i) & 1; bits.push(b); ones += b; }
    if (parity === 'even') bits.push(ones & 1);
    else if (parity === 'odd') bits.push((ones & 1) ^ 1);
    bits.push(1);                                       // stop bit (line high)
    return bits;
  }
  // bytes: array of ints transmitted back-to-back starting at t0 (us). Returns segments + level transitions.
  function build(bytes, baud, t0, parity) {
    const bitUs = 1e6 / baud, out = { bitUs, frames: [], edges: [], end: t0 };
    let t = t0, level = 1;
    out.edges.push([t, 1]);
    bytes.forEach((byte, idx) => {
      const bits = frameBits(byte, parity);
      const f = { idx, byte, t0: t, t1: t + bits.length * bitUs, bits };
      bits.forEach((b, k) => { if (b !== level) { out.edges.push([t + k * bitUs, level]); out.edges.push([t + k * bitUs, b]); level = b; } });
      t += bits.length * bitUs; out.frames.push(f);
    });
    out.edges.push([t, level]); out.end = t;
    return out;
  }
  // level at time t (us) for a waveform
  function levelAt(w, t) {
    for (const f of w.frames) if (t >= f.t0 && t < f.t1) return f.bits[Math.floor((t - f.t0) / w.bitUs)];
    return 1;
  }
  const api = { frameBits, build, levelAt };
  if (typeof module !== 'undefined') module.exports = api; else root.UartWave = api;
})(typeof window !== 'undefined' ? window : globalThis);
