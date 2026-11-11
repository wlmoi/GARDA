// node tests/browser_io_check.cjs <edge-exe> <url> <out.png> : clicks SW3 / holds KEY1 in SIMULATION and checks LEDs + safety panel
const { spawn } = require('child_process'); const fs = require('fs'); const os = require('os'); const path = require('path');
const [exe, url, out] = process.argv.slice(2); const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const prof = fs.mkdtempSync(path.join(os.tmpdir(), 'cdp-')); const p = spawn(exe, ['--headless=new', '--disable-gpu', '--remote-debugging-port=9334', `--user-data-dir=${prof}`, 'about:blank'], { stdio: 'ignore' });
  let t; for (let i = 0; i < 40; i++) { try { t = (await (await fetch('http://127.0.0.1:9334/json')).json()).find(x => x.type === 'page'); if (t) break; } catch { } await sleep(250); }
  const ws = new WebSocket(t.webSocketDebuggerUrl); await new Promise(r => ws.onopen = r); let id = 0; const pend = {}, errs = [];
  ws.onmessage = m => { const d = JSON.parse(m.data); if (d.id && pend[d.id]) pend[d.id](d.result); if (d.method === 'Runtime.exceptionThrown') errs.push(d.params.exceptionDetails.exception?.description); };
  const cmd = (method, params = {}) => new Promise(r => { pend[++id] = r; ws.send(JSON.stringify({ id, method, params })); });
  const ev = async e => (await cmd('Runtime.evaluate', { expression: e, awaitPromise: true })).result.value;
  await cmd('Runtime.enable'); await cmd('Emulation.setDeviceMetricsOverride', { width: 1400, height: 1500, deviceScaleFactor: 1, mobile: false });
  await cmd('Page.navigate', { url }); await sleep(2000);
  await ev("document.querySelector('#btnSim').click()"); await sleep(800);
  const state = () => ev("JSON.stringify({fc:S.safety.fc,leds:[...document.querySelectorAll('.led.on')].map(x=>x.title.split(' ')[0]),sw3:document.querySelector('.tgl:nth-child(4)').classList.contains('on'),k1:document.querySelector('#key1').classList.contains('on'),cell:document.querySelector('#safety').textContent.slice(0,260)})");
  console.log('idle    ', await state());
  await ev("document.querySelector('#sws button[data-i=\"3\"]').click()"); await sleep(900); console.log('SW3 on  ', await state());
  await ev("document.querySelector('#sws button[data-i=\"3\"]').click()"); await sleep(900);
  await ev("document.querySelector('#key1').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}))"); await sleep(900); console.log('KEY1 dn ', await state());
  fs.writeFileSync(out, Buffer.from((await cmd('Page.captureScreenshot', { format: 'png' })).data, 'base64'));
  await ev("document.querySelector('#key1').dispatchEvent(new PointerEvent('pointerup',{bubbles:true}))"); await sleep(900); console.log('KEY1 up ', await state());
  console.log('JS errors:', errs.length ? errs : 'none'); ws.close(); p.kill(); process.exit(0);
})();
