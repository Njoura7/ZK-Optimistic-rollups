// Regenerate the three dashboard figures used by the thesis.
//
// Requirements:
//   - the demo stack running: docker compose up --build -d
//   - playwright-core installed locally: npm install --no-save playwright-core
//   - a local Chromium/Edge executable (override with BROWSER_PATH)
//
// Run from this directory: node capture_dashboards.js
//
// Grafana scrolls its dashboard inside a nested container, so fullPage
// screenshots do not include the lower panels. This script scrolls that
// container explicitly and uses fixed clips for a reproducible framing.

const { chromium } = require('playwright-core');
const path = require('path');
const http = require('http');

const OUT = path.join(__dirname, 'dashboards');
const EXEC = process.env.BROWSER_PATH ||
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const GRAFANA = process.env.GRAFANA_URL || 'http://localhost:3001';
const FLASK = process.env.FLASK_URL || 'http://localhost:3000';

// Optional traffic injection so counters and latency panels are non-empty.
function inject(port, n) {
  return new Promise(resolve => {
    let done = 0;
    for (let i = 0; i < n; i++) {
      const body = JSON.stringify({ from: `img${i}`, to: `img${i + 1}`, value: 10 });
      const req = http.request({
        host: '127.0.0.1', port, path: '/tx', method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) }
      }, res => { res.resume(); if (++done === n) resolve(); });
      req.on('error', () => { if (++done === n) resolve(); });
      req.end(body);
    }
  });
}

async function loginGrafana(page) {
  await page.goto(GRAFANA + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('input[name="user"]', { timeout: 20000 });
  await page.fill('input[name="user"]', 'admin');
  await page.fill('input[name="password"]', 'admin');
  await page.getByRole('button', { name: /log in/i }).first().click();
  await page.waitForTimeout(4000);
}

(async () => {
  if (process.argv.includes('--with-traffic')) {
    await Promise.all([inject(5000, 500), inject(5001, 400)]);
    console.log('traffic injected: 500 ZK + 400 Optimistic transactions');
  }

  const browser = await chromium.launch({
    executablePath: EXEC, headless: true, args: ['--no-sandbox', '--disable-gpu']
  });
  const page = await browser.newPage({
    viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1
  });

  try {
    await loginGrafana(page);
    await page.goto(GRAFANA + '/d/zk-optimistic-comparison/', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.react-grid-item', { timeout: 30000 });
    await page.waitForTimeout(6000);

    const titles = await page.evaluate(() =>
      Array.from(document.querySelectorAll('.css-1x5lhtt-panel-title'))
        .map(e => e.textContent.trim()));
    console.log('top panel titles:', JSON.stringify(titles.slice(0, 8)));

    // Top: nav, dashboard title, and the two stat rows (8 panels).
    await page.screenshot({
      path: path.join(OUT, 'grafana-top-panels.png'),
      clip: { x: 0, y: 0, width: 1920, height: 570 }
    });
    console.log('wrote grafana-top-panels.png (1920x570)');

    // Scroll the nested Grafana container to reveal panels 10-14.
    const scrolled = await page.evaluate(() => {
      const grid = document.querySelector('.react-grid-layout');
      const cands = Array.from(document.querySelectorAll('*'))
        .filter(e => e.scrollHeight > e.clientHeight + 100 && e.clientHeight > 200);
      const target = cands.find(e => grid && e.contains(grid)) || cands[0];
      if (!target) return null;
      target.scrollTop = target.scrollHeight;
      return { cls: String(target.className), top: target.scrollTop };
    });
    console.log('scrolled dashboard container:', JSON.stringify(scrolled));
    await page.waitForTimeout(3000);

    // Bottom: transaction-rate comparison plus the four lower panels.
    await page.screenshot({
      path: path.join(OUT, 'grafana-bottom-panels.png'),
      clip: { x: 300, y: 110, width: 1555, height: 965 }
    });
    console.log('wrote grafana-bottom-panels.png (1555x965)');

    await page.goto(FLASK + '/', { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(3000);
    const flaskText = await page.evaluate(() => document.body.innerText);
    if (!flaskText.includes('MOCK IN TESTBED')) {
      throw new Error('Flask page did not show the mock-proof label; aborting capture');
    }
    await page.screenshot({
      path: path.join(OUT, 'flask-dashboard-overview.png'), fullPage: true
    });
    console.log('wrote flask-dashboard-overview.png');
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(e); process.exit(1); });
