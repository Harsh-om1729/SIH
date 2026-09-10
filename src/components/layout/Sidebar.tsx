import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Video,
  AlertTriangle,
  Crosshair,
  BarChart3,
  Shield,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';

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
  { label: 'Detections', to: '/detections', icon: AlertTriangle },
  { label: 'Zones', to: '/zones', icon: Crosshair },
  { label: 'Analytics', to: '/analytics', icon: BarChart3 },
];

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
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
          'fixed top-0 bottom-0 left-0 z-40 w-64 bg-[#05070a] border-r border-[#161924] flex flex-col transition-transform duration-200 ease-in-out lg:translate-x-0',
          isOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Brand / Header */}
        <div className="h-16 px-5 flex items-center justify-between border-b border-[#161924] bg-[#07090f]">
          <NavLink to="/" className="flex items-center gap-3 group" onClick={onClose}>
            <div className="w-9 h-9 rounded-xl bg-[#0e121c] border border-white/10 flex items-center justify-center text-accent-teal">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2 font-bold tracking-tight text-base text-white">
                <span>IBVAP</span>
                <span className="text-[10px] font-bold px-2 py-0.5 bg-accent-teal/15 text-accent-teal rounded-full border border-accent-teal/30">
                  AI
                </span>
              </div>
              <div className="text-[11px] text-text-dim leading-none mt-0.5">
                Tactical Command
              </div>
            </div>
          </NavLink>

          {/* Close button on mobile */}
          <button
            onClick={onClose}
            aria-label="Close sidebar navigation"
            className="lg:hidden p-1.5 rounded-lg text-text-muted hover:text-white hover:bg-white/[0.04] transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation List */}
        <nav className="flex-1 px-3 py-5 space-y-1.5 overflow-y-auto">
          <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-widest text-text-muted">
            Tactical Views
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
                    'group relative flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-colors select-none',
                    isActive
                      ? 'bg-[#0f1422] text-white font-semibold border-l-2 border-accent-teal'
                      : 'text-text-dim hover:text-white hover:bg-white/[0.04]'
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={cn(
                        'w-4 h-4 shrink-0 transition-colors',
                        isActive
                          ? 'text-accent-teal'
                          : 'text-text-muted group-hover:text-white'
                      )}
                    />
                    <span className="flex-1 truncate">{item.label}</span>

                    {item.badge && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#141a29] text-text-dim border border-white/10">
                        {item.badge}
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>

        {/* Simple System Status Footer */}
        <div className="p-3.5 border-t border-[#161924] bg-[#07090f] flex items-center justify-between text-xs font-mono">
          <span className="flex items-center gap-1.5 text-text-muted">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-green inline-block" />
            System Live
          </span>
          <span className="text-[10px] text-text-dim">IBVAP Core</span>
        </div>
      </aside>

    </>
  );
};
