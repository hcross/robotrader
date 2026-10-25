import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  badgeFor,
  formatMetric,
  formatOperational,
} from '../src/lib/provenance.js';

// --- Executable D12 rules -------------------------------------------------
assert.equal(formatMetric(null, 'MEASURED', 'money'), '—');
assert.equal(formatMetric(0, 'MEASURED', 'money'), '$0.00');
assert.equal(formatMetric(0, 'BOOTSTRAP', 'money'), '—');
assert.equal(formatMetric(undefined, null, 'number'), '—');
assert.equal(formatOperational(null, 'money'), '—');
assert.equal(formatOperational(0, 'money'), '$0.00');
assert.equal(badgeFor(null), 'UNATTRIBUTED');
assert.equal(badgeFor(undefined), 'UNATTRIBUTED');
assert.equal(badgeFor('BOOTSTRAP'), 'BOOTSTRAP');
assert.equal(badgeFor('MEASURED'), 'MEASURED');
assert.notEqual(badgeFor('BOOTSTRAP'), badgeFor(null));

// --- Static wiring --------------------------------------------------------
const here = dirname(fileURLToPath(import.meta.url));
const srcDir = resolve(here, '../src');

const files = {
  App: resolve(srcDir, 'App.jsx'),
  MasterOverview: resolve(srcDir, 'components/MasterOverview.jsx'),
  LeafAgentView: resolve(srcDir, 'components/LeafAgentView.jsx'),
  Dashboard: resolve(srcDir, 'components/Dashboard.jsx'),
};

const sources = Object.fromEntries(
  Object.entries(files).map(([name, path]) => [name, readFileSync(path, 'utf8')])
);

// App is part of the static scan (offline skeleton), but only the three
// rendering components must use the shared formatters.
for (const name of ['MasterOverview', 'LeafAgentView', 'Dashboard']) {
  const source = sources[name];
  assert.match(
    source,
    /from ['"]\.\.\/lib\/provenance['"]/,
    `${name} must import the shared provenance helper`
  );
  assert.match(source, /\bformatMetric\s*\(/, `${name} must invoke formatMetric`);
  assert.match(
    source,
    /\bformatOperational\s*\(/,
    `${name} must invoke formatOperational`
  );
}

const forbidden = [
  'realized_pnl_usd || 0',
  'sharpe_ratio || 0',
  'win_rate_pct || 0',
  '|| 11',
  '?? 24.5',
  "|| 'backtest_fixture'",
  '|| "backtest_fixture"',
  '25000',
  '19200',
  '5800',
  '0.232',
];

for (const [name, source] of Object.entries(sources)) {
  for (const pattern of forbidden) {
    assert.ok(
      !source.includes(pattern),
      `${name} reintroduced the forbidden fabricated default: ${pattern}`
    );
  }
}

console.log('provenance wiring OK');
