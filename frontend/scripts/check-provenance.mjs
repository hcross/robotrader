import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  ARTIFACT_KIND_POLICY_SANITY_CHECK,
  POLICY_SANITY_CHECK_LABEL,
  badgeFor,
  formatMetric,
  formatOperational,
} from '../src/lib/provenance.js';

// --- Executable D12 rules -------------------------------------------------
assert.equal(formatMetric(null, 'MEASURED', 'money'), '—');
assert.equal(formatMetric(0, 'MEASURED', 'money'), '$0.00');
assert.equal(formatMetric(0, 'BOOTSTRAP', 'money'), '—');
assert.equal(formatMetric(undefined, null, 'number'), '—');
assert.equal(formatMetric(10, 'BOGUS', 'money'), '—');
assert.equal(formatMetric(10, 'UNATTRIBUTED', 'money'), '—');
assert.equal(formatOperational(null, 'money'), '—');
assert.equal(formatOperational(undefined, 'money'), '—');
assert.equal(formatOperational(0, 'money'), '$0.00');
assert.equal(badgeFor(null), 'UNATTRIBUTED');
assert.equal(badgeFor(undefined), 'UNATTRIBUTED');
assert.equal(badgeFor('BOOTSTRAP'), 'BOOTSTRAP');
assert.equal(badgeFor('MEASURED'), 'MEASURED');
assert.equal(badgeFor('BOGUS'), 'UNATTRIBUTED');
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

// --- Fixture artefact labels ----------------------------------------------
assert.equal(ARTIFACT_KIND_POLICY_SANITY_CHECK, 'policy_sanity_check');
assert.equal(POLICY_SANITY_CHECK_LABEL, 'Policy sanity check');
for (const name of ['Dashboard', 'LeafAgentView']) {
  assert.match(
    sources[name],
    /POLICY_SANITY_CHECK_LABEL/,
    `${name} must render the shared policy sanity check label`
  );
}

const forbidden = [
  'Fixture Backtest Rust',
  'realized_pnl_usd || 0',
  'sharpe_ratio || 0',
  'win_rate_pct || 0',
  '|| 11',
  '?? 24.5',
  '?? 5.0',
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

// --- Simulated vault surface ---------------------------------------------
const leafView = sources.LeafAgentView;
assert.match(leafView, /SIMULATED/, 'LeafAgentView must show a SIMULATED badge');
assert.match(
  leafView,
  /address_is_spendable/,
  'LeafAgentView must render the non-spendable flag'
);
assert.match(
  leafView,
  /target_leaf_derivation_path/,
  'LeafAgentView must read the target leaf derivation path'
);

for (const [name, source] of Object.entries(sources)) {
  for (const forbiddenClaim of [
    'leaf.wallet_vault.leaf_derivation_path',
    'Zeroize RAM',
    'Enclave Rust',
  ]) {
    assert.ok(
      !source.includes(forbiddenClaim),
      `${name} reintroduced a false vault claim: ${forbiddenClaim}`
    );
  }
}

console.log('provenance wiring OK');
