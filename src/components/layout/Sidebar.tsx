import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Video,
  AlertTriangle,
  Crosshair,
  Users,
  BarChart3,
  Settings,
  Shield,
  Layers,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/Badge';
import { useAuth } from '@/components/auth/AuthProvider';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

interface NavItem {
  label: string;
  to: string;
  icon: React.ElementType;
  badge?: string;
}

const navItems: NavItem[] = [
  { label: 'Dashboard', to: '/', icon: LayoutDashboard },
  { label: 'Live Feeds', to: '/live', icon: Video, badge: '4 CAM' },
  { label: 'Incidents', to: '/incidents', icon: AlertTriangle },
  { label: 'Zones', to: '/zones', icon: Crosshair },
  { label: 'Watchlist', to: '/watchlist', icon: Users },
  { label: 'Analytics', to: '/analytics', icon: BarChart3 },
  { label: 'Settings', to: '/settings', icon: Settings },
];

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const { user } = useAuth();
  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-bg-primary/80 backdrop-blur-sm lg:hidden transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={cn(
          'fixed top-0 bottom-0 left-0 z-40 w-64 bg-bg-surface border-r border-border-subtle flex flex-col transition-transform duration-200 ease-in-out lg:translate-x-0',
          isOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Brand / Header */}
        <div className="h-16 px-5 flex items-center justify-between border-b border-border-subtle bg-bg-surface">
          <NavLink to="/" className="flex items-center gap-3 group" onClick={onClose}>
            <div className="p-2 rounded-sm bg-accent-teal/10 border border-accent-teal/30 text-accent-teal group-hover:border-accent-teal/60 transition-colors">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-1.5 font-bold tracking-wider text-base text-text-primary">
                <span>IBVAP</span>
                <span className="text-[10px] font-mono px-1.5 py-0.2 bg-accent-teal/10 text-accent-teal rounded-sm border border-accent-teal/20">
                  AI-CCTV
                </span>
              </div>
              <div className="text-[10px] font-mono text-text-dim tracking-tight">
                BORDER COMMAND v1.0
              </div>
            </div>
          </NavLink>

          {/* Close button on mobile */}
          <button
            onClick={onClose}
            aria-label="Close sidebar navigation"
            className="lg:hidden p-1.5 rounded-sm text-text-muted hover:text-text-primary hover:bg-bg-elevated transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Security Outpost Indicator */}
        <div className="px-4 py-3 border-b border-border-subtle/50 bg-bg-surface/50">
          <div className="flex items-center justify-between text-xs">
            <span className="font-mono text-[11px] text-text-dim">OPERATING SECTOR</span>
            <Badge variant="green" dot size="sm">
              ONLINE
            </Badge>
          </div>
          <div className="font-mono text-xs text-text-primary font-medium mt-1 truncate">
            SECTOR-NORTH · BOP-BRAVO
          </div>
        </div>

        {/* Navigation List */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          <div className="px-3 pb-2 text-[10px] font-mono uppercase tracking-wider text-text-muted">
            Command Center
          </div>

          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                onClick={onClose}
                className={({ isActive }) =>
                  cn(
                    'group relative flex items-center gap-3 px-3.5 py-2.5 rounded-sm text-xs font-medium transition-all select-none',
                    isActive
                      ? 'bg-accent-teal/10 text-accent-teal font-semibold shadow-sm'
                      : 'text-text-dim hover:text-text-primary hover:bg-bg-elevated/70'
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {/* Active Route Left Border Indicator */}
                    {isActive && (
                      <span className="absolute left-0 top-1 bottom-1 w-1 bg-accent-teal rounded-r-sm shadow-[0_0_8px_rgba(95,214,196,0.6)]" />
                    )}

                    <Icon
                      className={cn(
                        'w-4 h-4 transition-colors shrink-0',
                        isActive
                          ? 'text-accent-teal'
                          : 'text-text-muted group-hover:text-text-primary'
                      )}
                    />
                    <span className="flex-1 truncate">{item.label}</span>

                    {item.badge && (
                      <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-bg-elevated text-text-dim border border-border-subtle">
                        {item.badge}
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            );
          })}

          <div className="pt-4 px-3 pb-2 text-[10px] font-mono uppercase tracking-wider text-text-muted">
            Reference & Dev
          </div>

          <NavLink
            to="/design-system"
            onClick={onClose}
            className={({ isActive }) =>
              cn(
                'group relative flex items-center gap-3 px-3.5 py-2.5 rounded-sm text-xs font-medium transition-all select-none',
                isActive
                  ? 'bg-accent-teal/10 text-accent-teal font-semibold'
                  : 'text-text-dim hover:text-text-primary hover:bg-bg-elevated/70'
              )
            }
          >
            <Layers className="w-4 h-4 text-text-muted group-hover:text-text-primary" />
            <span className="flex-1 truncate">UI Design Tokens</span>
            <span className="font-mono text-[9px] px-1 py-0.5 rounded bg-accent-teal/10 text-accent-teal">
              DEV
            </span>
          </NavLink>
        </nav>

        {/* Air-Gapped Status & Operator Footer */}
        <div className="p-3 border-t border-border-subtle bg-bg-surface/80 space-y-2">
          {user && (
            <div className="flex items-center justify-between px-1 font-mono text-[10px]">
              <span className="text-text-dim truncate font-medium">{user.name}</span>
              <Badge
                variant={user.role === 'commander' ? 'teal' : 'green'}
                size="sm"
                className="py-0 text-[9px]"
              >
                {user.role.toUpperCase()}
              </Badge>
            </div>
          )}
          <div className="p-2 rounded-sm bg-bg-elevated border border-border-subtle space-y-1">
            <div className="flex items-center justify-between text-[10px] font-mono">
              <span className="text-text-dim">C2 STATUS:</span>
              <span className="text-accent-green font-bold">CONNECTED</span>
            </div>
            <div className="text-[10px] font-mono text-text-muted">
              LATENCY: 12ms · AES-256
            </div>
          </div>
        </div>
      </aside>
    </>
  );
};
