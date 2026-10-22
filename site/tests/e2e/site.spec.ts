import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const ROUTES = ['dwarf', 'gnome', 'human', 'night-elf', 'orc', 'tauren', 'troll', 'undead'];

test('race picker reaches every route and marks Skyborne as coming soon', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Choose your race');
  const hrefs = await page.locator('a.race').evaluateAll((as) => as.map((a) => a.getAttribute('href')));
  expect(hrefs.sort()).toEqual(ROUTES.map((r) => `/${r}/`).sort());
  await expect(page.getByText('Coming soon')).toHaveCount(2);
  for (const route of ROUTES) {
    const res = await page.goto(`/${route}/`);
    expect(res?.status()).toBe(200);
    await expect(page.locator('[aria-current="step"]')).toHaveCount(1);
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
  await expect(page.getByText('Step 2 of')).toBeVisible();
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
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Human 1–30 route');
});

test('high contrast is remembered across pages and reloads', async ({ page }) => {
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
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
  await page.getByLabel('High contrast').check();
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-contrast', 'high');
  expect(violations).toEqual([]);
});

test('steps show objectives, levels and plain-language gap reasons', async ({ page }) => {
  await page.goto('/human/');
  await expect(page.locator('.steps[data-loaded="true"]')).toBeVisible();
  await expect(page.locator('li.step.complete').first()).toContainText(/: (kill|collect|use) /);
  await expect(page.locator('h2.zone .zone-levels').first()).toHaveText(/^Levels \d+–\d+$/);
  await expect(page.locator('label[for="route-progress"]')).toContainText('about level 1');
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
