import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth, UserRole } from '@/components/auth/AuthProvider';
import { Button } from '@/components/ui/Button';
import {
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
    <div className="min-h-screen bg-black text-text-primary flex items-center justify-center p-4 bg-tactical-grid ambient-glow relative overflow-hidden">
      {/* Background Ambience 3D Glow Orbs */}
      <div className="absolute w-[600px] h-[600px] bg-accent-teal/10 rounded-full blur-[140px] pointer-events-none -top-40 -left-40" />
      <div className="absolute w-[600px] h-[600px] bg-accent-cyan/10 rounded-full blur-[140px] pointer-events-none -bottom-40 -right-40" />

      <div className="w-full max-w-md space-y-6 relative z-10">
        {/* Defense Header & Emblem */}
        <div className="text-center space-y-3">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-b from-[#161622] to-[#08080d] border border-white/20 border-t-white/30 text-accent-teal shadow-[0_10px_25px_rgba(0,240,255,0.2)] mb-1">
            <Radio className="w-7 h-7 animate-pulse text-accent-teal" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-white drop-shadow-md">
            IBVAP Gateway
          </h1>
          <p className="text-xs text-text-dim max-w-sm mx-auto leading-relaxed">
            Intelligent Border Video Analytics & Perimeter Surveillance Console
          </p>
        </div>

        {/* 3D Auth Card */}
        <div className="card-3d p-8 rounded-2xl border border-white/15 bg-gradient-to-b from-[#0e0e16] to-[#060609] shadow-[0_20px_50px_rgba(0,0,0,0.9),0_0_40px_rgba(0,240,255,0.05)] space-y-6 backdrop-blur-xl">
          {/* Quick 1-Click Evaluator Access */}
          <div className="space-y-3 p-4 rounded-xl bg-black/60 border border-white/10 shadow-inner">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-accent-teal flex items-center gap-1.5 tracking-wide">
                <Zap className="w-3.5 h-3.5 text-accent-teal" />
                INSTANT DEMO ACCESS
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-accent-teal/15 text-accent-teal border border-accent-teal/30">1-CLICK</span>
            </div>
            <div className="grid grid-cols-2 gap-2.5">
              <button
                type="button"
                onClick={() => handleQuickLogin('commander')}
                className="flex items-center justify-center gap-2 p-2.5 rounded-xl bg-gradient-to-b from-[#141d24] to-[#0b1015] hover:from-[#1b2732] hover:to-[#0f1820] border border-accent-teal/40 hover:border-accent-teal text-accent-teal text-xs font-semibold transition-all duration-200 shadow-[0_4px_12px_rgba(0,240,255,0.15)] active:translate-y-0.5 group"
              >
                <Server className="w-3.5 h-3.5 group-hover:scale-110 transition-transform text-accent-teal" />
                <span>Commander</span>
              </button>

              <button
                type="button"
                onClick={() => handleQuickLogin('operator')}
                className="flex items-center justify-center gap-2 p-2.5 rounded-xl bg-gradient-to-b from-[#102219] to-[#09150e] hover:from-[#173023] hover:to-[#0c1e14] border border-accent-green/40 hover:border-accent-green text-accent-green text-xs font-semibold transition-all duration-200 shadow-[0_4px_12px_rgba(0,255,136,0.15)] active:translate-y-0.5 group"
              >
                <UserCheck className="w-3.5 h-3.5 group-hover:scale-110 transition-transform text-accent-green" />
                <span>Operator</span>
              </button>
            </div>
          </div>

          {/* Credentials Form */}
          <form onSubmit={handleManualLogin} className="space-y-4">
            {errorMsg && (
              <div className="p-3 rounded-xl bg-accent-red/15 border border-accent-red/40 text-accent-red text-xs font-medium">
                {errorMsg}
              </div>
            )}

            {/* Outpost / Sector Selector */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-text-dim block">
                Assigned Border Outpost:
              </label>
              <select
                value={sector}
                onChange={(e) => setSector(e.target.value)}
                className="w-full px-3.5 py-2.5 text-xs bg-[#0b0b12] border border-white/15 rounded-xl text-white focus:outline-none focus:border-accent-teal focus:ring-1 focus:ring-accent-teal shadow-inner cursor-pointer transition-all"
              >
                <option value="BOP-Alpha / Sector 4">BOP-Alpha (Jammu Frontier · Sector 4)</option>
                <option value="BOP-Bravo / Sector 2">BOP-Bravo (Punjab Frontier · Sector 2)</option>
                <option value="Checkpost-Charlie">Checkpost-Charlie (Western Corridor)</option>
                <option value="BOP-Delta / Riverine">BOP-Delta (Riverine Sector · Night-Vision)</option>
              </select>
            </div>

            {/* Role Clearance Selection */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-text-dim block">Clearance Level:</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setRole('commander');
                    setEmail('commander@ibvap.mil');
                  }}
                  className={`p-2.5 rounded-xl border text-xs font-semibold transition-all duration-200 ${
                    role === 'commander'
                      ? 'bg-accent-teal/20 border-accent-teal text-accent-teal shadow-[0_0_15px_rgba(0,240,255,0.25)]'
                      : 'bg-[#0b0b12] border-white/10 text-text-dim hover:text-white hover:border-white/20'
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
                  className={`p-2.5 rounded-xl border text-xs font-semibold transition-all duration-200 ${
                    role === 'operator'
                      ? 'bg-accent-green/20 border-accent-green text-accent-green shadow-[0_0_15px_rgba(0,255,136,0.25)]'
                      : 'bg-[#0b0b12] border-white/10 text-text-dim hover:text-white hover:border-white/20'
                  }`}
                >
                  Operator (Level 2)
                </button>
              </div>
            </div>

            {/* Operator ID Input */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-text-dim block">Operator ID / Email:</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3.5 py-2.5 text-xs bg-[#0b0b12] border border-white/15 rounded-xl text-white placeholder:text-text-muted focus:outline-none focus:border-accent-teal focus:ring-1 focus:ring-accent-teal shadow-inner transition-all font-mono"
                placeholder="operator@ibvap.mil"
                required
              />
            </div>

            {/* Password Input */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-text-dim block">Passkey:</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3.5 py-2.5 text-xs bg-[#0b0b12] border border-white/15 rounded-xl text-white placeholder:text-text-muted focus:outline-none focus:border-accent-teal focus:ring-1 focus:ring-accent-teal shadow-inner transition-all font-mono"
                placeholder="••••••••••••"
                required
              />
            </div>

            <Button
              type="submit"
              variant="primary"
              size="md"
              className="w-full justify-center text-xs font-bold mt-3 py-3"
            >
              <Lock className="w-3.5 h-3.5 mr-2" />
              Sign In to Console
            </Button>
          </form>
        </div>

        {/* Footer */}
        <div className="text-center text-xs text-text-dim flex items-center justify-center gap-2">
          <span>Encrypted Defense Gateway</span>
          <span>·</span>
          <span>Status:</span>
          <span className="text-accent-green font-semibold flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-green animate-pulse" />
            Operational
          </span>
        </div>
      </div>
    </div>
  );
};

