// node tests/test_wave.js : verifies reconstructed UART bit order against known frames
const assert = require('assert');
const W = require('../web/wave.js');
assert.deepStrictEqual(W.frameBits(0xA5), [0, 1, 0, 1, 0, 0, 1, 0, 1, 1]);       // LSB first
assert.deepStrictEqual(W.frameBits(0x01), [0, 1, 0, 0, 0, 0, 0, 0, 0, 1]);
assert.deepStrictEqual(W.frameBits(0x80), [0, 0, 0, 0, 0, 0, 0, 0, 1, 1]);
assert.deepStrictEqual(W.frameBits(0x03, 'even'), [0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 1]);  // parity bit sits before stop
assert.deepStrictEqual(W.frameBits(0x03, 'odd'), [0, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1]);
const w = W.build([0xA5, 0x5A], 115200, 0);
assert.ok(Math.abs(w.bitUs - 8.6806) < 1e-3);
assert.strictEqual(w.frames.length, 2);
assert.ok(Math.abs(w.frames[0].t1 - 10 * w.bitUs) < 1e-9);                        // byte boundary after 10 bits
assert.ok(Math.abs(w.frames[1].t0 - w.frames[0].t1) < 1e-9);
assert.strictEqual(W.levelAt(w, 0.5 * w.bitUs), 0);                               // start bit low
assert.strictEqual(W.levelAt(w, 1.5 * w.bitUs), 1);                               // D0 of 0xA5 = 1
assert.strictEqual(W.levelAt(w, 2.5 * w.bitUs), 0);                               // D1 = 0
assert.strictEqual(W.levelAt(w, 9.5 * w.bitUs), 1);                               // stop high
console.log('wave.js OK');
