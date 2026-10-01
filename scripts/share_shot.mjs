// Screenshot HTML pages at 1200x630 with headless Chrome (used by make_share_cards.py).
//   node scripts/share_shot.mjs <profile-dir> <page.html> <out.png> [<page.html> <out.png> ...]
// Chrome picks its own debugging port (--remote-debugging-port=0) and writes it to
// <profile>/DevToolsActivePort, so this never attaches to another Chrome on the machine.
import { spawn } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

const [profile, ...pairs] = process.argv.slice(2);
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const chrome = spawn(CHROME, ["--headless=new", "--remote-debugging-port=0", `--user-data-dir=${profile}`,
  "--no-first-run", "--no-default-browser-check", "--hide-scrollbars", "about:blank"], { stdio: "ignore" });
let wsUrl;
for (let i = 0; i < 200 && !wsUrl; i++) {
  try {
    const [port, path] = (await readFile(`${profile}/DevToolsActivePort`, "utf8")).trim().split("\n");
    wsUrl = `ws://127.0.0.1:${port}${path}`;
  } catch { await sleep(100); }
}
if (!wsUrl) { chrome.kill(); throw new Error("Chrome did not start"); }
const ws = new WebSocket(wsUrl); await new Promise((r) => (ws.onopen = r));
let id = 0; const waiting = new Map();
ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && waiting.has(m.id)) { const w = waiting.get(m.id); waiting.delete(m.id); m.error ? w.rej(new Error(m.error.message)) : w.res(m.result); } };
const call = (method, params = {}, sessionId) => new Promise((res, rej) => { const i = ++id; waiting.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method, params, sessionId })); });
const { targetId } = await call("Target.createTarget", { url: "about:blank" });
const { sessionId } = await call("Target.attachToTarget", { targetId, flatten: true });
const s = (m, p) => call(m, p, sessionId);
await s("Page.enable");
await s("Emulation.setDeviceMetricsOverride", { width: 1200, height: 630, deviceScaleFactor: 1, mobile: false });
for (let i = 0; i < pairs.length; i += 2) {
  await s("Page.navigate", { url: pathToFileURL(pairs[i]).href });
  await sleep(300);
  await s("Runtime.evaluate", { expression: "(async()=>{await document.fonts.ready;await Promise.all([...document.images].map(i=>i.complete?1:new Promise(r=>i.onload=i.onerror=r)));await new Promise(r=>setTimeout(r,150));return 1})()", awaitPromise: true });
  const { data } = await s("Page.captureScreenshot", { format: "png", clip: { x: 0, y: 0, width: 1200, height: 630, scale: 1 } });
  await writeFile(pairs[i + 1], Buffer.from(data, "base64"));
}
ws.close(); chrome.kill();
