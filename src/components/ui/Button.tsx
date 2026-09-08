import React from 'react';
import { cn } from '@/lib/utils';
import { Loader2 } from 'lucide-react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = 'primary',
      size = 'md',
      isLoading = false,
      leftIcon,
      rightIcon,
      disabled,
      children,
      ...props
    },
    ref
  ) => {
    const baseStyles =
      'inline-flex items-center justify-center font-medium transition-all duration-150 rounded-sm focus:outline-none focus:ring-1 focus:ring-accent-teal/60 disabled:opacity-50 disabled:cursor-not-allowed select-none active:translate-y-[1px]';

    const variants = {
      primary:
        'bg-accent-teal text-bg-primary hover:bg-accent-teal/90 shadow-sm shadow-accent-teal/10 font-semibold',
      secondary:
        'bg-bg-elevated text-text-primary border border-border-subtle hover:border-text-muted hover:bg-bg-surface',
      ghost:
        'bg-transparent text-text-dim hover:text-text-primary hover:bg-bg-elevated border border-transparent',
      danger:
        'bg-accent-red/15 text-accent-red border border-accent-red/40 hover:bg-accent-red/25 hover:border-accent-red/60',
    };

    const sizes = {
      sm: 'text-xs px-2.5 py-1 gap-1.5 h-7',
      md: 'text-sm px-3.5 py-1.5 gap-2 h-9',
      lg: 'text-base px-5 py-2.5 gap-2.5 h-11',
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(baseStyles, variants[variant], sizes[size], className)}
        {...props}
      >
        {isLoading ? (
          <Loader2 className="w-4 h-4 animate-spin text-current" />
        ) : (
          leftIcon && <span className="inline-flex shrink-0">{leftIcon}</span>
        )}
        <span>{children}</span>
        {!isLoading && rightIcon && (
          <span className="inline-flex shrink-0">{rightIcon}</span>
        )}
      </button>
    );
  }
);

Button.displayName = 'Button';
