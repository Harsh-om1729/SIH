import React from 'react';
import { cn } from '@/lib/utils';

export interface TabItem {
  id: string;
  label: React.ReactNode;
  icon?: React.ReactNode;
  count?: number | string;
  disabled?: boolean;
}

export interface TabsProps {
  items: TabItem[];
  activeTab: string;
  onChange: (tabId: string) => void;
  variant?: 'underline' | 'pill';
  className?: string;
}

export const Tabs: React.FC<TabsProps> = ({
  items,
  activeTab,
  onChange,
  variant = 'underline',
  className,
}) => {
  if (variant === 'pill') {
    return (
      <div
        className={cn(
          'inline-flex p-1 bg-bg-surface border border-border-subtle rounded-sm gap-1',
          className
        )}
      >
        {items.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              disabled={tab.disabled}
              onClick={() => onChange(tab.id)}
              className={cn(
                'flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-sm transition-all select-none',
                isActive
                  ? 'bg-bg-elevated text-accent-teal shadow-sm border border-border-subtle'
                  : 'text-text-dim hover:text-text-primary hover:bg-bg-elevated/50 border border-transparent',
                tab.disabled && 'opacity-40 cursor-not-allowed'
              )}
            >
              {tab.icon && <span className="w-3.5 h-3.5">{tab.icon}</span>}
              <span>{tab.label}</span>
              {tab.count !== undefined && (
                <span
                  className={cn(
                    'px-1.5 py-0.2 rounded font-mono text-[10px]',
                    isActive
                      ? 'bg-accent-teal/20 text-accent-teal'
                      : 'bg-bg-elevated text-text-muted'
                  )}
                >
                  {tab.count}
                </span>
              )}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div
      className={cn(
        'flex border-b border-border-subtle w-full gap-6 px-1',
        className
      )}
    >
      {items.map((tab) => {
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            disabled={tab.disabled}
            onClick={() => onChange(tab.id)}
            className={cn(
              'group relative flex items-center gap-2 py-3 text-xs font-medium transition-colors select-none tracking-wide',
              isActive
                ? 'text-accent-teal font-semibold'
                : 'text-text-dim hover:text-text-primary',
              tab.disabled && 'opacity-40 cursor-not-allowed'
            )}
          >
            {tab.icon && <span className="w-3.5 h-3.5">{tab.icon}</span>}
            <span>{tab.label}</span>
            {tab.count !== undefined && (
              <span
                className={cn(
                  'px-1.5 py-0.5 rounded font-mono text-[10px]',
                  isActive
                    ? 'bg-accent-teal/20 text-accent-teal'
                    : 'bg-bg-elevated text-text-muted'
                )}
              >
                {tab.count}
              </span>
            )}
            {/* Active bottom border indicator */}
            {isActive && (
              <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-accent-teal shadow-[0_0_8px_rgba(95,214,196,0.5)]" />
            )}
          </button>
        );
      })}
    </div>
  );
};
