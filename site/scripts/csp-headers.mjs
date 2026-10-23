// After `astro build`: write dist/_headers (Cloudflare Pages) with a CSP that allows Astro's inline
// scripts by hash only. Run by `npm run build`.
import { createHash } from 'node:crypto';
import { readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

/** Bodies of the inline (no src) <script> elements in an HTML document. */
export function inlineScripts(html) {
  return [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi)].map((m) => m[1]);
}

/** The _headers file for every page, given the HTML of all pages. */
export function buildHeaders(htmlPages) {
  const hashes = new Set();
  for (const html of htmlPages) {
    for (const body of inlineScripts(html)) {
      hashes.add(`'sha256-${createHash('sha256').update(body).digest('base64')}'`);
    }
  }
  const csp = [
    "default-src 'self'",
    `script-src 'self' ${[...hashes].sort().join(' ')}`.trim(),
    // React sets pin positions as style attributes; styles cannot run code.
    "style-src 'self' 'unsafe-inline'",
    // Quest videos: the thumbnail from YouTube, and the player (privacy-enhanced mode) once the viewer presses play.
    "img-src 'self' data: https://i.ytimg.com",
    "frame-src https://www.youtube-nocookie.com",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join('; ') + ';';
  return [
    '/*',
    `  Content-Security-Policy: ${csp}`,
    '  X-Content-Type-Options: nosniff',
    '  Referrer-Policy: strict-origin-when-cross-origin',
    '  X-Frame-Options: DENY',
    '  Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()',
    '',
  ].join('\n');
}

function htmlFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = join(dir, e.name);
    return e.isDirectory() ? htmlFiles(p) : e.name.endsWith('.html') ? [p] : [];
  });
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const dist = fileURLToPath(new URL('../dist', import.meta.url));
  const pages = htmlFiles(dist).map((f) => readFileSync(f, 'utf8'));
  writeFileSync(join(dist, '_headers'), buildHeaders(pages), 'utf8');
  console.log(`wrote dist/_headers for ${pages.length} pages`);
}
