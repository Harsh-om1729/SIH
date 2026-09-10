import React from 'react';
import { cn } from '@/lib/utils';

export interface CardProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  action?: React.ReactNode;
  footer?: React.ReactNode;
  variant?: 'default' | 'elevated' | 'bordered';
  bodyClassName?: string;
}

export const Card = React.forwardRef<HTMLDivElement, CardProps>(
  (
    {
      className,
      title,
      subtitle,
      action,
      footer,
      variant = 'default',
      bodyClassName,
      children,
      ...props
    },
    ref
  ) => {
    const variants = {
      default: 'card-3d rounded-2xl',
      elevated: 'card-3d rounded-2xl bg-[#0b0e16] border-white/10 shadow-lg',
      bordered: 'card-3d rounded-2xl border-white/15 shadow-md',
    };

    const hasHeader = Boolean(title || subtitle || action);

    return (
      <div
        ref={ref}
        className={cn(
          'text-text-primary overflow-hidden transition-colors duration-100 relative',
          variants[variant],
          className
        )}
        {...props}
      >
        {hasHeader && (
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/[0.06] bg-[#07090f]">
            <div className="space-y-0.5">
              {title && (
                <div className="font-semibold text-sm tracking-tight text-text-primary flex items-center gap-2">
                  {title}
                </div>
              )}
              {subtitle && (
                <div className="text-xs text-text-dim leading-relaxed">{subtitle}</div>
              )}
            </div>
            {action && <div className="flex items-center gap-2">{action}</div>}
          </div>
        )}


        <div className={cn('p-5', bodyClassName)}>{children}</div>

        {footer && (
          <div className="px-5 py-3.5 border-t border-white/[0.08] bg-black/40 text-xs text-text-dim flex items-center justify-between">
            {footer}
          </div>
        )}
      </div>
    );
  }
);

Card.displayName = 'Card';
