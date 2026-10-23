import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

/** The settings live behind the gear button. */
async function openSettings(page: Page) {
  const gear = page.getByRole('button', { name: 'Settings' });
  if ((await gear.getAttribute('aria-expanded')) !== 'true') await gear.click();
}

const ROUTES = ['dwarf', 'gnome', 'human', 'night-elf', 'orc', 'skyborne-alliance', 'skyborne-horde', 'tauren',
  'troll', 'undead'];

test('race picker reaches every route, Skyborne once per faction', async ({ page }) => {
  test.setTimeout(90_000);  // opens all ten route pages, some with a thousand steps
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(/^Level 1 to \d+, the fast way$/);
  const hrefs = await page.locator('a.race').evaluateAll((as) => as.map((a) => a.getAttribute('href')));
  expect(hrefs.sort()).toEqual(ROUTES.map((r) => `/${r}/`).sort());
  await expect(page.locator('section.faction a.race', { hasText: 'Skyborne' })).toHaveCount(2);
  for (const route of ROUTES) {
    const res = await page.goto(`/${route}/`);
    expect(res?.status()).toBe(200);
    await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();  // the island is hydrated
    await expect(page.locator('li.step[aria-current="step"]')).toHaveCount(1);
  }
});

test('a marked step stays marked after reload', async ({ page }) => {
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  const first = page.locator('li.step').first();
  await first.getByRole('button', { name: 'Step 1 done' }).click();
  await expect(first).toHaveClass(/done/);
  await expect(page.locator('li.step').nth(1)).toHaveAttribute('aria-current', 'step');
  await page.reload();
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  await expect(page.locator('li.step').first()).toHaveClass(/done/);
  await expect(page.locator('.progress-step')).toHaveText(/^Step 2 \/ \d+$/);
  // Progress is per route.
  await page.goto('/orc/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  await expect(page.locator('li.step').first()).not.toHaveClass(/done/);
});

test('Space marks the current step done and is announced; the shortcut can be turned off', async ({ page }) => {
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  await page.keyboard.press('Space');
  await expect(page.locator('li.step').first()).toHaveClass(/done/);
  await expect(page.locator('#announcer')).toContainText('Step 1 done. Next:');
  await openSettings(page);
  await page.getByLabel('Space marks the current step done').uncheck();
  await page.locator('h2.zone').first().click();
  await page.keyboard.press('Space');
  await expect(page.locator('li.step').nth(1)).not.toHaveClass(/done/);
});

test('skip link jumps to the current step', async ({ page }) => {
  await page.goto('/human/');
  await page.keyboard.press('Tab');
  const skip = page.getByRole('link', { name: 'Skip to current step' });
  await expect(skip).toBeFocused();
  await expect(skip).toHaveAttribute('href', '#current-step');
  await expect(page.locator('#current-step')).toHaveAttribute('aria-current', 'step');
});

test('map pins are keyboard buttons that lead to their step', async ({ page }) => {
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  const pin = page.locator('.pin.current');
  await expect(pin).toHaveCount(1);
  await expect(pin).toHaveAttribute('aria-label', /^1 .*, steps? 1[ ,]/);
  await pin.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('li.step').first()).toBeFocused();
  await page.getByRole('button', { name: 'Zoom in' }).click();
  await expect(page.getByRole('button', { name: 'Zoom out' })).toBeEnabled();
});

test('high contrast switch sets the contrast theme', async ({ page }) => {
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  await openSettings(page);
  await page.getByLabel('High contrast').check();
  await expect(page.locator('html')).toHaveAttribute('data-contrast', 'high');
});

for (const path of ['/', '/human/']) {
  test(`axe finds no violations on ${path}`, async ({ page }) => {
    test.setTimeout(90_000); // ~700 steps: the scan is slow when tests run in parallel
    await page.goto(path);
    await page.waitForLoadState('networkidle');
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'])
      .analyze();
    expect(results.violations.map((v) => `${v.id}: ${v.nodes.length} ${v.nodes[0]?.target}`)).toEqual([]);
  });

  test(`no horizontal scroll at 320px on ${path}`, async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 800 });
    await page.goto(path);
    await page.waitForLoadState('networkidle');
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });
}

test('a merged pin shows the current step number', async ({ page }) => {
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  await page.getByRole('button', { name: 'Step 1 done' }).click();
  await page.getByRole('button', { name: 'Step 2 done' }).click();
  const pin = page.locator('.pin.current');
  await expect(pin).toHaveText(/^3/);
  await pin.click();
  await expect(page.locator('li.step').nth(2)).toBeFocused();
});

test('the route still works when the browser blocks site data', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, 'localStorage', { get() { throw new DOMException('denied', 'SecurityError'); } });
  });
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  expect(await page.locator('li.step').count()).toBeGreaterThan(100);
  await page.getByRole('button', { name: 'Step 1 done' }).click();
  await expect(page.locator('li.step').first()).toHaveClass(/done/);
  expect(errors).toEqual([]);
});

test('after a mouse click, Space marks the next step instead of undoing the clicked one', async ({ page }) => {
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  await page.getByRole('button', { name: 'Step 1 done' }).click();
  await page.keyboard.press('Space');
  await expect(page.locator('li.step').first()).toHaveClass(/done/);
  await expect(page.locator('li.step').nth(1)).toHaveClass(/done/);
});

test('holding Space marks only one step', async ({ page }) => {
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  await page.keyboard.down('Space');
  await page.keyboard.down('Space');
  await page.keyboard.down('Space');
  await page.keyboard.up('Space');
  await expect(page.locator('li.step.done')).toHaveCount(1);
});

test('the current pin sits on the current step coordinates', async ({ page }) => {
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  for (const n of [1, 2, 3, 4]) await page.getByRole('button', { name: `Step ${n} done` }).click();
  const xy = (await page.locator('li.step.current .xy').textContent())!.split(', ').map(Number);
  const style = (await page.locator('.pin.current').getAttribute('style'))!;
  const [left, top] = [...style.matchAll(/(left|top): ([\d.]+)%/g)].map((m) => Number(m[2]));
  expect(Math.abs(left - xy[0])).toBeLessThan(0.06);
  expect(Math.abs(top - xy[1])).toBeLessThan(0.06);
});

test('route page has one main landmark and one h1', async ({ page }) => {
  await page.goto('/human/');
  await expect(page.locator('main')).toHaveCount(1);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(/^Human 1–\d+ leveling route$/);
});

test('high contrast is remembered across pages and reloads', async ({ page }) => {
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  await openSettings(page);
  await page.getByLabel('High contrast').check();
  await page.goto('/');
  await expect(page.locator('html')).toHaveAttribute('data-contrast', 'high');
  await page.goto('/orc/');
  await expect(page.getByLabel('High contrast')).toBeChecked();
});

test('the current step has a report link to a prefilled GitHub issue', async ({ page }) => {
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  const links = page.getByRole('link', { name: /Report this step/ });
  await expect(links).toHaveCount(1);
  const href = (await links.getAttribute('href'))!;
  expect(href).toMatch(/^https:\/\/github\.com\/Erenkinik\/forever-leveling\/issues\/new\?title=%5Bhuman%5D\+Step\+1/);
  await expect(page.locator('li.step.current .report')).toHaveCount(1);
});

test('pages work under the CSP from dist/_headers', async ({ page }) => {
  const { readFileSync } = await import('node:fs');
  const headers = readFileSync(new URL('../../dist/_headers', import.meta.url), 'utf8');
  const csp = headers.match(/Content-Security-Policy: (.*)/)![1];
  await page.route('**/*', async (route) => {
    const res = await route.fetch();
    await route.fulfill({ response: res, headers: { ...res.headers(), 'content-security-policy': csp } });
  });
  const violations: string[] = [];
  page.on('console', (m) => { if (/Content Security Policy|Refused to/i.test(m.text())) violations.push(m.text()); });
  await page.goto('/');
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  await openSettings(page);
  await page.getByLabel('High contrast').check();
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-contrast', 'high');
  expect(violations).toEqual([]);
  await page.unrouteAll({ behavior: 'ignoreErrors' });  // requests still in flight must not fail after the test
});

test('steps show objectives, levels and plain-language gap reasons', async ({ page }) => {
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  await expect(page.locator('li.step.complete').first()).toContainText(/: (kill|collect|use) /);
  await expect(page.locator('h2.zone .zone-levels').first()).toHaveText(/^Levels \d+–\d+( · about .+)?$/);
  await expect(page.locator('.progress-level')).toHaveText('Level 1');
  const gap = page.locator('li.step.gap').first();
  await expect(gap).toContainText('Skip for now:');
  await expect(gap).not.toContainText(/quest \d+:/);
});

test('search finds a quest and jumps to its step', async ({ page }) => {
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  await page.getByLabel('Find a quest or NPC').fill('kobold camp');
  await expect(page.locator('#step-search-count')).toHaveText(/found$/);
  const first = page.locator('.search-results button').first();
  await expect(first).toContainText('Kobold Camp Cleanup');
  await first.click();
  await expect(page.locator('li.step:focus')).toContainText('Kobold Camp Cleanup');
  // Typing a space in the search box must not mark a step.
  await page.getByLabel('Find a quest or NPC').fill('');
  await page.getByLabel('Find a quest or NPC').press('Space');
  await expect(page.locator('li.step.done')).toHaveCount(0);
});

test('the map shows the zone art with a labelled current pin', async ({ page }) => {
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  const map = page.locator('.map.art');
  await expect(map).toHaveCount(1);
  await expect(map).toHaveAttribute('style', /url\("?\/maps\/1429\.webp"?\)/);
  const res = await page.request.get('/maps/1429.webp');
  expect(res.status()).toBe(200);
  expect(res.headers()['content-type']).toContain('image/webp');
  await expect(page.locator('.pin.current .pin-label')).toHaveText('Deputy Willem');
  await expect(page.locator('.map-note')).toContainText('Blizzard Entertainment');
});

test('the race switcher lists every race and moves to the chosen one', async ({ page }) => {
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();  // the island is hydrated
  const button = page.getByRole('button', { name: /Change race/ });
  await expect(button).toHaveAttribute('aria-expanded', 'false');
  await button.click();
  await expect(button).toHaveAttribute('aria-expanded', 'true');
  await expect(page.locator('.race-panel a')).toHaveCount(ROUTES.length);
  await expect(page.locator('.race-panel a[aria-current="page"]')).toHaveText('Human');
  await page.keyboard.press('Escape');
  await expect(button).toHaveAttribute('aria-expanded', 'false');
  await expect(button).toBeFocused();
  await button.click();
  await page.locator('.race-panel').getByRole('link', { name: 'Orc' }).click();
  await expect(page).toHaveURL(/\/orc\/$/);
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Orc');
});

test('skipped steps are never the current step', async ({ page }) => {
  await page.goto('/orc/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  await expect(page.locator('li.step.current')).not.toHaveClass(/gap/);
  await expect(page.locator('.tag', { hasText: 'Unverified' })).toHaveCount(0);
});

test('the quest scroll under the map lists what to do for the current quest', async ({ page }) => {
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  const scroll = page.locator('.quest-scroll:not(.video-scroll)');
  await expect(scroll.locator('h3')).toHaveText('A Threat Within');
  const items = scroll.locator('ol > li');
  await expect(items.first()).toContainText('Talk to Deputy Willem at 48.2, 42.9 and accept the quest.');
  await expect(items.first()).toHaveAttribute('aria-current', 'step');
  await expect(items.last()).toContainText('turn the quest in.');
  // Step 2 turns the same quest in: the scroll stays on it and marks the last line as current.
  await page.getByRole('button', { name: 'Step 1 done' }).click();
  await expect(scroll.locator('h3')).toHaveText('A Threat Within');
  await expect(items.last()).toHaveAttribute('aria-current', 'step');
});

test('race crests and the parchment are served', async ({ page }) => {
  for (const path of ['/art/crest-human.webp', '/art/crest-orc.webp', '/art/parchment.webp']) {
    const res = await page.request.get(path);
    expect(res.status(), path).toBe(200);
  }
});

test('items to collect show their game icon, and map pins use the game quest icons', async ({ page }) => {
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  const icon = page.locator('li.step .item img.item-icon').first();
  await expect(icon).toBeVisible();
  const src = (await icon.getAttribute('src'))!;
  expect(src).toMatch(/^\/art\/items\/\d+\.webp$/);
  expect((await page.request.get(src)).status()).toBe(200);
  await expect(page.locator('.pin.current img')).toHaveAttribute('src', '/art/icon-accept.webp');
  // Turn-ins of quests not done yet show the faint grey "?": with the first nine steps done the player is out
  // collecting, and the quest's turn-in back at the start shows the grey "?".
  for (let n = 1; n <= 9; n++) await page.getByRole('button', { name: `Step ${n} done` }).click();
  const progress = page.locator('.pin.progress img').first();
  await expect(progress).toHaveAttribute('src', '/art/icon-progress.webp');
  expect((await page.request.get('/art/icon-progress.webp')).status()).toBe(200);
});

test('high contrast keeps the quest parchment', async ({ page }) => {
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  await openSettings(page);
  await page.getByLabel('High contrast').check();
  const bg = await page.locator('.quest-scroll:not(.video-scroll)').evaluate((el) => getComputedStyle(el).backgroundImage);
  expect(bg).toContain('parchment.webp');
});

test('the map shades where the current quest objectives are done', async ({ page }) => {
  await page.goto('/tauren/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  // The Hunt Begins: the plainstrider area belongs to the current quest.
  expect(await page.locator('.areas .area.active ellipse').count()).toBeGreaterThan(3);
  const opacity = await page.locator('.areas .area.active').evaluate((el) => Number(getComputedStyle(el).opacity));
  expect(opacity).toBeGreaterThan(0.2);
  expect(opacity).toBeLessThan(0.6);
});

test('choosing a class shows only its own class quests, and the choice is remembered', async ({ page }) => {
  await page.goto('/orc/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  const pick = page.getByRole('combobox', { name: 'Class' });
  await expect(pick).toHaveValue('');
  const tags = page.locator('li.step .tag.class');
  expect(await tags.allTextContents()).toEqual(expect.arrayContaining(['Warlock', 'Shaman']));
  await pick.selectOption('Warlock');
  const left = await tags.allTextContents();
  expect(left.length).toBeGreaterThan(0);
  expect(left.every((t) => t.split(', ').includes('Warlock'))).toBe(true);
  await page.reload();
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'Class' })).toHaveValue('Warlock');
});

test('exploration mode shows the quests off the route on the map, and is remembered', async ({ page }) => {
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  const toggle = page.getByRole('button', { name: 'All quests' });
  await expect(toggle).toHaveAttribute('aria-pressed', 'false');
  await expect(page.locator('.pin.optional')).toHaveCount(0);
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-pressed', 'true');
  expect(await page.locator('.pin.optional').count()).toBeGreaterThan(0);
  await expect(page.locator('.pin.optional').first()).toHaveAttribute('aria-label', /^Optional quest: .+, level \d+$/);
  await page.reload();
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  await expect(page.getByRole('button', { name: 'All quests' })).toHaveAttribute('aria-pressed', 'true');
});

test('a session plan marks where the chosen time runs out, and zones show their time', async ({ page }) => {
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  await expect(page.locator('.session-plan p')).toContainText(/About .+ left on this route/);
  await expect(page.locator('.zone-levels').first()).toContainText(/about \d+ (h|min)/);
  await expect(page.locator('.tag.session')).toHaveCount(0);
  await page.getByLabel('Play session').selectOption('60');
  await expect(page.locator('.session-plan p')).toContainText(/Steps 1–\d+, to about level \d+/);
  await expect(page.locator('.tag.session')).toHaveCount(1);
});

test('a dungeon entrance on the map shows its quests in a panel', async ({ page }) => {
  const { readFileSync } = await import('node:fs');
  const route = JSON.parse(readFileSync(new URL('../../src/data/human.json', import.meta.url), 'utf8'));
  // Every step before the route first reaches Westfall is done, so the map shows Westfall and the Deadmines.
  const at = route.steps.findIndex((s: { mapId: number; type: string }) => s.mapId === 1436 && s.type !== 'travel');
  const done = route.steps.slice(0, at).map((s: { id: string }) => s.id);
  await page.addInitScript((ids) => window.localStorage.setItem('fxp:v1:human', JSON.stringify(ids)), done);
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  const entrance = page.getByRole('button', { name: /^Deadmines, dungeon, \d+ quests$/ });
  await expect(entrance.locator('img.dungeon-quests')).toHaveCount(1);  // the "!" for its quests
  await entrance.click();
  const panel = page.getByRole('dialog', { name: 'Deadmines' });
  await expect(panel).toBeVisible();
  expect(await panel.locator('li').count()).toBeGreaterThan(0);
  await expect(panel).toContainText(/On your route: step \d+|Not on this route/);
  await page.keyboard.press('Escape');
  await expect(panel).toHaveCount(0);
  await expect(entrance).toBeFocused();
});

test('on a phone the map is a sheet opened from the Map button', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/orc/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  const map = page.locator('#route-map');
  await expect(map).not.toBeInViewport();
  const button = page.getByRole('button', { name: 'Map', exact: true });
  await button.click();
  const sheet = page.getByRole('dialog', { name: /^Map of / });
  await expect(sheet).toBeInViewport();
  await expect(sheet.getByRole('button', { name: 'Close map' })).toBeFocused();
  expect(await new AxeBuilder({ page }).include('#route-map').analyze().then((r) => r.violations)).toEqual([]);
  await page.keyboard.press('Escape');
  await expect(sheet).toHaveCount(0);
  await expect(button).toBeFocused();
});

test('where a quest starts, its video waits on parchment until play is pressed', async ({ page }) => {
  const { readFileSync } = await import('node:fs');
  const found = ROUTES.flatMap((id) => {
    const route = JSON.parse(readFileSync(new URL(`../../src/data/${id}.json`, import.meta.url), 'utf8'));
    const at = route.steps.findIndex((s: { type: string; video?: unknown }) => s.type === 'accept' && s.video);
    return at < 0 ? [] : [{ id, done: route.steps.slice(0, at).map((s: { id: string }) => s.id),
                            video: route.steps[at].video }];
  });
  test.skip(found.length === 0, 'no quest videos yet (python -m pipeline videos)');
  const { id, done, video } = found[0];
  await page.route('https://i.ytimg.com/**', (r) => r.fulfill({ status: 204 }));
  await page.route('https://www.youtube-nocookie.com/**', (r) => r.fulfill({ contentType: 'text/html', body: '' }));
  await page.addInitScript(([key, ids]) => window.localStorage.setItem(key, JSON.stringify(ids)),
                           [`fxp:v1:${id}`, done] as const);
  await page.goto(`/${id}/`);
  const panel = page.getByRole('region', { name: 'Quest video' });
  await expect(panel.locator('iframe')).toHaveCount(0);
  await panel.getByRole('button', { name: `Play video: ${video.title}` }).click();
  await expect(panel.locator('iframe')).toHaveAttribute('src', new RegExp(`youtube-nocookie.com/embed/${video.id}`));
});
