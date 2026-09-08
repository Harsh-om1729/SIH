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
      default: 'bg-bg-surface border-border-subtle',
      elevated: 'bg-bg-elevated border-border-subtle hover:border-text-muted/40 transition-colors',
      bordered: 'bg-bg-surface border-accent-teal/30',
    };

    const hasHeader = Boolean(title || subtitle || action);

    return (
      <div
        ref={ref}
        className={cn(
          'rounded-sm border text-text-primary overflow-hidden shadow-none',
          variants[variant],
          className
        )}
        {...props}
      >
        {hasHeader && (
          <div className="flex items-center justify-between px-4 py-3 border-b border-border-subtle bg-bg-surface/50">
            <div className="space-y-0.5">
              {title && (
                <div className="font-semibold text-sm tracking-wide text-text-primary">
                  {title}
                </div>
              )}
              {subtitle && (
                <div className="text-xs text-text-dim">{subtitle}</div>
              )}
            </div>
            {action && <div className="flex items-center gap-2">{action}</div>}
          </div>
        )}

        <div className={cn('p-4', bodyClassName)}>{children}</div>

        {footer && (
          <div className="px-4 py-2.5 border-t border-border-subtle bg-bg-surface/30 text-xs text-text-dim flex items-center justify-between">
            {footer}
          </div>
        )}
      </div>
    );
  }
);

Card.displayName = 'Card';
