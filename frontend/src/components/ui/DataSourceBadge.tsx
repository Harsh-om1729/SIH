import React from 'react';

/**
 * Says out loud where the rows on this page came from.
 *
 * Without it a page served from mockIncidents.ts is visually identical to one
 * served from incidents.db — which is how you end up demonstrating invented
 * data believing it is your model's output.
 */
export const DataSourceBadge: React.FC<{ isMock: boolean; error?: string | null }> = ({
  isMock,
  error,
}) => {
  if (!isMock) {
    return (
      <span
        title="Served by the IBVAP backend"
        className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 text-[10px] font-mono uppercase tracking-wider"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
        Live data
      </span>
    );
  }
  return (
    <span
      title={error ? `Backend unreachable: ${error}` : 'Backend unreachable'}
      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border border-amber-500/40 bg-amber-500/10 text-amber-300 text-[10px] font-mono uppercase tracking-wider"
    >
      <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
      Demo data — backend offline
    </span>
  );
};
