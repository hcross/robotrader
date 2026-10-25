// Provenance rendering rules (design D12).
//
// A performance value is displayed only when its block declares a source that
// is not BOOTSTRAP and not missing. A BOOTSTRAP block renders an em dash no
// matter what number is stored (including a zero token count or cost); an
// unattributed block renders an em dash too, with a distinct badge.
//
// Operational values (capital, deployed, dry powder, ratios, counts, balances,
// allocation weights) carry no population provenance and use the null-aware
// formatter without a badge.

export const METRIC_SOURCES = Object.freeze([
  'MEASURED',
  'SIMULATED',
  'FIXTURE',
  'BOOTSTRAP',
]);

export const DRAWER_SOURCES = Object.freeze([
  'LLM',
  'DETERMINISTIC_FALLBACK',
  'BOOTSTRAP',
]);

export const EM_DASH = '—';

const KNOWN_SOURCES = new Set([...METRIC_SOURCES, ...DRAWER_SOURCES]);

export function badgeFor(source) {
  return KNOWN_SOURCES.has(source) ? source : 'UNATTRIBUTED';
}

function formatValue(value, kind) {
  const numeric = Number(value);
  switch (kind) {
    case 'money':
      return `$${numeric.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`;
    case 'signedMoney':
      return `${numeric >= 0 ? '+' : '-'}$${Math.abs(numeric).toFixed(2)}`;
    case 'cost':
      return `$${numeric.toFixed(6)}`;
    case 'rate':
      return `${numeric.toFixed(1)}%`;
    case 'percent':
      return `${numeric.toFixed(2)}%`;
    case 'integer':
      return `${Math.trunc(numeric)}`;
    case 'number':
    default:
      return numeric.toFixed(2);
  }
}

export function formatMetric(value, source, kind = 'number') {
  if (source === null || source === undefined) return EM_DASH;
  if (source === 'BOOTSTRAP') return EM_DASH;
  if (value === null || value === undefined) return EM_DASH;
  return formatValue(value, kind);
}

export function formatOperational(value, kind = 'number') {
  if (value === null || value === undefined) return EM_DASH;
  return formatValue(value, kind);
}
