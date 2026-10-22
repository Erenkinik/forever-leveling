import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { test } from 'node:test';

import { buildHeaders, inlineScripts } from '../../scripts/csp-headers.mjs';

const sha = (s: string) => `'sha256-${createHash('sha256').update(s).digest('base64')}'`;

test('inlineScripts finds inline scripts and skips external ones', () => {
  const html = '<script>a()</script><script src="/x.js"></script><script type="module">\nb()\n</script>';
  assert.deepEqual(inlineScripts(html), ['a()', '\nb()\n']);
});

test('buildHeaders allows exactly the inline scripts by hash and sets the security headers', () => {
  const headers: string = buildHeaders(['<script>a()</script>', '<script>a()</script><script>c()</script>']);
  const csp = headers.split('\n').find((l) => l.includes('Content-Security-Policy'))!;
  assert.ok(headers.startsWith('/*\n'));
  assert.ok(csp.includes(`script-src 'self' ${[sha('a()'), sha('c()')].sort().join(' ')};`), csp);
  for (const part of ["default-src 'self'", "object-src 'none'", "frame-ancestors 'none'", "base-uri 'self'"]) {
    assert.ok(csp.includes(part), part);
  }
  for (const h of ['X-Content-Type-Options: nosniff', 'Referrer-Policy: strict-origin-when-cross-origin',
                   'X-Frame-Options: DENY', 'Permissions-Policy:']) {
    assert.ok(headers.includes(h), h);
  }
});
