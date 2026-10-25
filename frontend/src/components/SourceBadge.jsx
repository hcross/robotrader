import React from 'react';
import { badgeFor } from '../lib/provenance';

const BADGE_STYLES = {
  MEASURED: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40',
  SIMULATED: 'bg-purple-500/15 text-purple-300 border-purple-500/40',
  FIXTURE: 'bg-blue-500/15 text-blue-300 border-blue-500/40',
  LLM: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40',
  DETERMINISTIC_FALLBACK: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
  BOOTSTRAP: 'bg-gray-700/40 text-gray-300 border-gray-500/50 border-dashed',
  UNATTRIBUTED: 'bg-red-500/15 text-red-300 border-red-500/40',
};

// The BOOTSTRAP and UNATTRIBUTED badges differ in text, colour and border
// style, so a seeded block can never be mistaken for a measured one.
const SourceBadge = ({ source, className = '' }) => {
  const label = badgeFor(source);
  const style = BADGE_STYLES[label] || BADGE_STYLES.UNATTRIBUTED;
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded border text-[10px] font-mono uppercase tracking-wide ${style} ${className}`}
    >
      {label}
    </span>
  );
};

export default SourceBadge;
