import React, { useState } from 'react';
import { cn } from '@/lib/utils';

/**
 * An encrypted evidence image served by /api/v1/incidents/{id}/evidence/...
 *
 * Evidence can legitimately be missing — a pruned snapshots/ folder, a key
 * rotated after capture, or an incident recorded without a crop — so a
 * failure renders an explicit "unavailable" tile instead of the browser's
 * broken-image icon, which an operator could read as a camera fault.
 */
interface EvidenceImageProps {
  src?: string;
  alt: string;
  className?: string;
  /** Thumbnail-sized fallback text. */
  compact?: boolean;
}

export const EvidenceImage: React.FC<EvidenceImageProps> = ({ src, alt, className, compact }) => {
  // Keyed on src so switching to another incident/frame retries cleanly.
  const [failedSrc, setFailedSrc] = useState<string | undefined>(undefined);

  if (!src || failedSrc === src) {
    return (
      <div
        role="img"
        aria-label={`${alt} — ${src ? 'unavailable' : 'not recorded'}`}
        className={cn(
          'flex items-center justify-center bg-black text-text-muted font-mono text-center',
          compact ? 'text-[8px] leading-tight p-0.5' : 'text-xs p-4',
          className
        )}
      >
        {src ? 'Evidence unavailable' : 'No evidence recorded'}
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      decoding="async"
      onError={() => setFailedSrc(src)}
      className={cn('bg-black', className)}
    />
  );
};
