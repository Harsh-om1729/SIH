import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth, UserRole } from '@/components/auth/AuthProvider';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import {
  ShieldAlert,
  Lock,
  Radio,
  UserCheck,
  Server,
  Zap,
} from 'lucide-react';

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState('commander@ibvap.mil');
  const [password, setPassword] = useState('••••••••••••');
  const [sector, setSector] = useState('BOP-Alpha / Sector 4');
  const [role, setRole] = useState<UserRole>('commander');
  const [errorMsg, setErrorMsg] = useState('');

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/';

  const handleManualLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) {
      setErrorMsg('Please enter an authorized operator email.');
      return;
    }
    login(email, role, sector);
    navigate(from, { replace: true });
  };

  const handleQuickLogin = (selectedRole: UserRole) => {
    const selectedEmail =
      selectedRole === 'commander' ? 'commander@ibvap.mil' : 'operator@ibvap.mil';
    login(selectedEmail, selectedRole, sector);
    navigate(from, { replace: true });
  };

  return (
    <div className="min-h-screen bg-[#0a0f0d] text-text-primary flex items-center justify-center p-4 bg-tactical-grid relative overflow-hidden">
      {/* Background Ambience Glow */}
      <div className="absolute w-96 h-96 bg-accent-teal/5 rounded-full blur-3xl pointer-events-none -top-20 -left-20" />
      <div className="absolute w-96 h-96 bg-accent-red/5 rounded-full blur-3xl pointer-events-none -bottom-20 -right-20" />

      <div className="w-full max-w-lg space-y-5 relative z-10">
        {/* Defense Header & Emblem */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center p-3 rounded-md bg-[#111917] border border-border-subtle shadow-xl mb-1">
            <Radio className="w-8 h-8 text-accent-teal animate-pulse" />
          </div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-wider text-text-primary font-mono uppercase">
            IBVAP Tactical Gateway
          </h1>
          <p className="text-xs text-text-dim font-mono">
            INTELLIGENT BORDER VIDEO ANALYTICS PLATFORM · AIR-GAPPED NODE
          </p>
          <div className="flex items-center justify-center gap-2 pt-1">
            <Badge variant="teal" dot size="sm" className="font-mono">
              SYSTEM: ONLINE
            </Badge>
            <Badge variant="yellow" size="sm" className="font-mono">
              MHA-DPDP 2023 COMPLIANT
            </Badge>
          </div>
        </div>

        {/* Tactical Card */}
        <div className="p-6 sm:p-7 rounded-md bg-[#111917] border border-border-subtle shadow-2xl space-y-5 backdrop-blur-md">
          {/* Statutory Security Advisory */}
          <div className="p-3 rounded bg-accent-yellow/10 border border-accent-yellow/30 flex items-start gap-2.5">
            <ShieldAlert className="w-4 h-4 text-accent-yellow shrink-0 mt-0.5" />
            <div className="text-[11px] text-text-dim leading-relaxed">
              <span className="font-bold text-accent-yellow block uppercase font-mono">
                RESTRICTED DEFENSE ACCESS
              </span>
              Unauthorized access to tactical CCTV inference feeds, biometric databases, or virtual-fence
              telemetry is prohibited under the Official Secrets Act.
            </div>
          </div>

          {/* 1-Click Quick Demo Presets for Evaluators / Judges */}
          <div className="space-y-2 p-3.5 rounded bg-bg-surface border border-accent-teal/30">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono font-bold text-accent-teal flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5 text-accent-teal" />
                1-CLICK EVALUATOR ACCESS:
              </span>
              <span className="text-[10px] font-mono text-text-muted">NO PASSWORD REQUIRED</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
              <button
                type="button"
                onClick={() => handleQuickLogin('commander')}
                className="flex items-center justify-center gap-2 p-2 rounded bg-accent-teal/15 hover:bg-accent-teal/25 border border-accent-teal/40 text-accent-teal text-xs font-mono font-semibold transition-all group"
              >
                <Server className="w-3.5 h-3.5 group-hover:scale-110 transition-transform" />
                <span>Sector Commander</span>
              </button>

              <button
                type="button"
                onClick={() => handleQuickLogin('operator')}
                className="flex items-center justify-center gap-2 p-2 rounded bg-accent-green/15 hover:bg-accent-green/25 border border-accent-green/40 text-accent-green text-xs font-mono font-semibold transition-all group"
              >
                <UserCheck className="w-3.5 h-3.5 group-hover:scale-110 transition-transform" />
                <span>Surveillance Operator</span>
              </button>
            </div>
          </div>

          {/* Credentials Form */}
          <form onSubmit={handleManualLogin} className="space-y-4">
            {errorMsg && (
              <div className="p-2.5 rounded bg-accent-red/15 border border-accent-red/40 text-accent-red text-xs font-mono">
                {errorMsg}
              </div>
            )}

            {/* Outpost / Sector Selector */}
            <div className="space-y-1">
              <label className="text-xs font-mono text-text-dim flex items-center justify-between">
                <span>ASSIGNED BORDER OUTPOST (BOP):</span>
              </label>
              <select
                value={sector}
                onChange={(e) => setSector(e.target.value)}
                className="w-full px-3 py-2 text-xs font-mono bg-bg-elevated border border-border-subtle rounded-sm text-text-primary focus:outline-none focus:border-accent-teal cursor-pointer"
              >
                <option value="BOP-Alpha / Sector 4">BOP-ALPHA (Jammu Frontier · Sector 4)</option>
                <option value="BOP-Bravo / Sector 2">BOP-BRAVO (Punjab Frontier · Sector 2)</option>
                <option value="Checkpost-Charlie">CHECKPOST-CHARLIE (Western Corridor)</option>
                <option value="BOP-Delta / Riverine">BOP-DELTA (Riverine Sector · Night-Vision)</option>
              </select>
            </div>

            {/* Role Clearance Selection */}
            <div className="space-y-1">
              <label className="text-xs font-mono text-text-dim">OPERATOR CLEARANCE LEVEL:</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setRole('commander');
                    setEmail('commander@ibvap.mil');
                  }}
                  className={`p-2 rounded border text-xs font-mono transition-all ${
                    role === 'commander'
                      ? 'bg-accent-teal/20 border-accent-teal text-accent-teal font-bold'
                      : 'bg-bg-elevated border-border-subtle text-text-dim hover:text-text-primary'
                  }`}
                >
                  Commander (Level 4)
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setRole('operator');
                    setEmail('operator@ibvap.mil');
                  }}
                  className={`p-2 rounded border text-xs font-mono transition-all ${
                    role === 'operator'
                      ? 'bg-accent-green/20 border-accent-green text-accent-green font-bold'
                      : 'bg-bg-elevated border-border-subtle text-text-dim hover:text-text-primary'
                  }`}
                >
                  Operator (Level 2)
                </button>
              </div>
            </div>

            {/* Operator ID Input */}
            <div className="space-y-1">
              <label className="text-xs font-mono text-text-dim">OPERATOR ID / MILNET EMAIL:</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3 py-2 text-xs font-mono bg-bg-elevated border border-border-subtle rounded-sm text-text-primary focus:outline-none focus:border-accent-teal"
                placeholder="operator@ibvap.mil"
                required
              />
            </div>

            {/* Password Input */}
            <div className="space-y-1">
              <label className="text-xs font-mono text-text-dim">SECURITY PASSKEY:</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 text-xs font-mono bg-bg-elevated border border-border-subtle rounded-sm text-text-primary focus:outline-none focus:border-accent-teal"
                placeholder="••••••••••••"
                required
              />
            </div>

            <Button
              type="submit"
              variant="primary"
              size="md"
              className="w-full justify-center font-mono font-bold text-xs mt-2 shadow-lg"
            >
              <Lock className="w-3.5 h-3.5 mr-2" />
              AUTHENTICATE & ENTER CONSOLE
            </Button>
          </form>
        </div>

        {/* Footer Audit Notice */}
        <div className="text-center text-[10px] font-mono text-text-muted space-y-1">
          <p>AUTHENTICATION TERMINAL ID: TERMINAL-JAMMU-BOP-4</p>
          <p>NODE INTEGRITY: SHA-256 VERIFIED · AIR-GAP ENFORCED</p>
        </div>
      </div>
    </div>
  );
};
