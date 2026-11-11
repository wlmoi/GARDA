// Headless Edge/Chrome check over CDP (no dependencies; needs Node >= 22).
// usage: node tests/browser_check.cjs <edge-exe> <url> <out-prefix> [--sim-demo]
const { spawn } = require('child_process'); const fs = require('fs'); const os = require('os'); const path = require('path');
const [exe, url, outp] = process.argv.slice(2); const simDemo = process.argv.includes('--sim-demo');
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const prof = fs.mkdtempSync(path.join(os.tmpdir(), 'cdp-'));
  const p = spawn(exe, ['--headless=new', '--disable-gpu', '--remote-debugging-port=9333', `--user-data-dir=${prof}`, 'about:blank'], { stdio: 'ignore' });
  let targets; for (let i = 0; i < 40; i++) { try { targets = await (await fetch('http://127.0.0.1:9333/json')).json(); if (targets.find(t => t.type === 'page')) break; } catch { } await sleep(250); }
  const ws = new WebSocket(targets.find(t => t.type === 'page').webSocketDebuggerUrl); await new Promise(r => ws.onopen = r);
  let id = 0; const pend = {}, logs = [];
  ws.onmessage = m => { const d = JSON.parse(m.data); if (d.id && pend[d.id]) pend[d.id](d.result); if (d.method === 'Runtime.exceptionThrown') logs.push('EXC ' + JSON.stringify(d.params.exceptionDetails.exception?.description || d.params.exceptionDetails.text)); if (d.method === 'Runtime.consoleAPICalled' && d.params.type === 'error') logs.push('CONSOLE ' + JSON.stringify(d.params.args.map(a => a.value || a.description))); };
  const cmd = (method, params = {}) => new Promise(r => { pend[++id] = r; ws.send(JSON.stringify({ id, method, params })); });
  await cmd('Runtime.enable'); await cmd('Page.enable');
  for (const [name, w, h] of [['desktop', 1500, 1900], ['mobile', 400, 2800]]) {
    await cmd('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 1, mobile: w < 600 });
    await cmd('Page.navigate', { url }); await sleep(2500);
    if (simDemo) { await cmd('Runtime.evaluate', { expression: "document.querySelector('#btnSim').click()", awaitPromise: false }); await sleep(800);
      await cmd('Runtime.evaluate', { expression: "document.querySelector('#demoBtn').click()" }); await sleep(900); }
    await sleep(2500);
    const r = await cmd('Runtime.evaluate', { expression: "JSON.stringify({badge:document.querySelector('#modeBadge').textContent,packets:document.querySelectorAll('#plist div').length,steps:document.querySelectorAll('#steps li').length,verdict:document.querySelector('#verdict').textContent,hscroll:document.documentElement.scrollWidth>innerWidth})" });
    console.log(name, r.result.value);
    const shot = await cmd('Page.captureScreenshot', { format: 'png' }); fs.writeFileSync(`${outp}_${name}.png`, Buffer.from(shot.data, 'base64'));
  }
  console.log('console errors:', logs.length ? logs : 'none'); ws.close(); p.kill(); process.exit(0);
})();
