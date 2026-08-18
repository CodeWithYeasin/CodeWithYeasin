import { chromium } from 'playwright';
import fs from 'node:fs';

const URL = 'file://' + new URL('./index.html', import.meta.url).pathname;
const OUT = new URL('./shots/', import.meta.url).pathname;
fs.mkdirSync(OUT, { recursive: true });

const errors = [];
const browser = await chromium.launch({ args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1152, height: 648 }, deviceScaleFactor: 1 });
page.on('pageerror', e => errors.push('pageerror: ' + e.message));
page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });

await page.goto(URL);
await page.waitForTimeout(1200);
await page.screenshot({ path: `${OUT}/01-title.png` });

// start
await page.keyboard.press('Enter');
await page.waitForTimeout(900);
const mode1 = await page.evaluate(() => window.__game.mode);
console.log('mode after Enter:', mode1);

// walk around a bit
for (const k of ['ArrowLeft', 'ArrowUp', 'ArrowRight', 'ArrowDown']) {
  await page.keyboard.down(k); await page.waitForTimeout(420); await page.keyboard.up(k);
}
await page.waitForTimeout(400);
await page.screenshot({ path: `${OUT}/02-hub.png` });

// collision check: try to walk into a wall for a long time, confirm we stay in-bounds
const before = await page.evaluate(() => ({ ...window.__game.player }));
await page.keyboard.down('ArrowUp'); await page.waitForTimeout(2500); await page.keyboard.up('ArrowUp');
const after = await page.evaluate(() => ({ ...window.__game.player }));
const inBounds = await page.evaluate(() => {
  const p = window.__game.player;
  return p.x > 0 && p.y > 0 && p.x < 80 * 16 && p.y < 74 * 16;
});
console.log('walk up moved y:', (before.y - after.y).toFixed(1), 'inBounds:', inBounds);

// teleport helper
const tp = (x, y) => page.evaluate(([x, y]) => {
  window.__game.player.x = x * 16 + 8;
  window.__game.player.y = y * 16 + 8;
  window.__game.cam.x = x * 16 - 192; window.__game.cam.y = y * 16 - 108;
}, [x, y]);

// dialogue
await tp(36, 46);
await page.waitForTimeout(350);
await page.keyboard.press('e');
await page.waitForTimeout(1500);
await page.screenshot({ path: `${OUT}/03-dialogue.png` });
const dlgOpen = await page.evaluate(() => window.__game.mode === 'dialogue');
const dlgHtml = await page.evaluate(() => document.getElementById('dlgText').innerHTML.length);
console.log('dialogue open:', dlgOpen, 'chars rendered:', dlgHtml);
await page.keyboard.press('Escape');
await page.waitForTimeout(200);

const ZONE_ENTS = {
  origin: [[12, 41], [20, 41], [16, 47]],
  arcane: [[36, 23], [44, 23], [40, 28]],
  shadow: [[60, 41], [68, 41], [64, 47]],
  forge:  [[36, 61], [44, 61], [40, 66]],
};
const SHARD_AT = { origin: [16, 43], arcane: [40, 25], shadow: [64, 43], forge: [40, 63] };

for (const [zone, spots] of Object.entries(ZONE_ENTS)) {
  for (const [ex, ey] of spots) {
    await tp(ex, ey + 1);
    await page.waitForTimeout(180);
    // exhaust every page of dialogue
    for (let i = 0; i < 12; i++) {
      await page.keyboard.press('e');
      await page.waitForTimeout(140);
      const m = await page.evaluate(() => window.__game.mode);
      if (m !== 'dialogue') break;
    }
    await page.waitForTimeout(120);
  }
  const spawned = await page.evaluate(z => window.__game.shardEnts.some(s => s.zone === z), zone);
  console.log(`${zone}: shard spawned =`, spawned);
  if (zone === 'origin') await page.screenshot({ path: `${OUT}/04-shard-spawn.png` });
  const [sx, sy] = SHARD_AT[zone];
  await tp(sx, sy);
  await page.waitForTimeout(400);
  const got = await page.evaluate(z => window.__game.shards.has(z), zone);
  console.log(`${zone}: shard collected =`, got);
}

const gate = await page.evaluate(() => ({ open: window.__game.gateOpen, n: window.__game.shards.size }));
console.log('after 4 shards:', gate);
await page.waitForTimeout(300);
await page.screenshot({ path: `${OUT}/05-gate.png` });

// beacon → ending
await tp(40, 9);
await page.waitForTimeout(400);
await page.screenshot({ path: `${OUT}/06-beacon.png` });
for (let i = 0; i < 8; i++) {
  await page.keyboard.press('e');
  await page.waitForTimeout(500);
  const m = await page.evaluate(() => window.__game.mode);
  if (m === 'end') break;
}
await page.waitForTimeout(700);
await page.screenshot({ path: `${OUT}/07-ending.png` });
const ended = await page.evaluate(() => window.__game.mode === 'end');
console.log('reached ending:', ended);

// mobile viewport sanity
const m = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
await m.goto(URL); await m.waitForTimeout(900);
await m.screenshot({ path: `${OUT}/08-mobile.png` });
await m.close();

console.log('\nERRORS:', errors.length ? errors : 'none');
await browser.close();
process.exit(errors.length ? 1 : 0);
