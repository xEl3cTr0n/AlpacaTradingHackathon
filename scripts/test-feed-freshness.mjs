import assert from 'node:assert/strict';
import test from 'node:test';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { tradeAge } = require(`${process.env.WORKSPACE_TEST_BUILD_DIR}/feed-freshness.js`);
const now = Date.parse('2026-09-15T09:00:00Z');
test('age reflects exchange trade timestamp, not retrieval time', () => {
  assert.deepEqual(tradeAge('2026-09-15T08:59:55Z', now), {label: 'Last trade 5s ago', stale: false});
  assert.deepEqual(tradeAge('2026-09-14T20:00:00Z', now), {label: 'Last trade 13h 0m ago', stale: true});
});
test('missing, invalid and future timestamps never look fresh', () => {
  for (const value of [undefined, 'bad', '2026-09-16T09:00:00Z']) assert.equal(tradeAge(value, now).stale, true);
});
