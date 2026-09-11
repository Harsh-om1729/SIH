import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

export type UserRole = 'operator' | 'commander';

export interface AuthUser {
  name: string;
  email: string;
  role: UserRole;
  sector: string;
  clearanceLevel: string;
  token: string;
}

interface AuthContextType {
  user: AuthUser | null;
  isAuthenticated: boolean;
  login: (email: string, role: UserRole, sector?: string) => void;
  logout: () => void;
  switchRole: (role: UserRole) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const AUTH_STORAGE_KEY = 'ibvap_auth_user';

export const DEFAULT_COMMANDER: AuthUser = {
  name: 'Capt. Neeraj S.',
  email: 'commander@ibvap.mil',
  role: 'commander',
  sector: 'BOP-Alpha / Sector 4',
  clearanceLevel: 'TOP-SECRET // LEVEL-4',
  token: 'tk_sec_c2_908842',
};

export const DEFAULT_OPERATOR: AuthUser = {
  name: 'Sub-Insp. Rajesh K.',
  email: 'operator@ibvap.mil',
  role: 'operator',
  sector: 'BOP-Alpha / Sector 4',
  clearanceLevel: 'SECRET-TACTICAL // LEVEL-2',
  token: 'tk_sec_op_447210',
};

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  // Pre-seed authenticated user from localStorage or fallback to DEFAULT_COMMANDER
  const [user, setUser] = useState<AuthUser | null>(() => {
    try {
      const saved = localStorage.getItem(AUTH_STORAGE_KEY);
      if (saved) {
        return JSON.parse(saved);
      }
    } catch {
      // ignore JSON parse error
    }
    // NOTE: falling back to a signed-in commander means RequireAuth never
    // actually blocks anyone and /login is unreachable in normal use. That is
    // deliberate for the demo, but it is NOT authentication: there is no user
    // store and no login endpoint in this system. What actually guards the
    // data is IBVAP_API_TOKEN on the API — see integration/api.py.
    return DEFAULT_COMMANDER;
  });

  useEffect(() => {
    if (user) {
      try {
        localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(user));
      } catch {
        // ignore
      }
    } else {
      localStorage.removeItem(AUTH_STORAGE_KEY);
    }
  }, [user]);

  const login = (email: string, role: UserRole, sector = 'BOP-Alpha / Sector 4') => {
    const isCommander = role === 'commander';
    const newUser: AuthUser = {
      name: isCommander ? 'Capt. Neeraj S.' : 'Sub-Insp. Rajesh K.',
      email,
      role,
      sector,
      clearanceLevel: isCommander ? 'TOP-SECRET // LEVEL-4' : 'SECRET-TACTICAL // LEVEL-2',
      token: `tk_sec_${role}_${Math.floor(100000 + Math.random() * 900000)}`,
    };
    setUser(newUser);
  };

  const logout = () => {
    setUser(null);
  };

  const switchRole = (newRole: UserRole) => {
    if (!user) return;
    const isCommander = newRole === 'commander';
    setUser({
      ...user,
      role: newRole,
      name: isCommander ? 'Capt. Neeraj S.' : 'Sub-Insp. Rajesh K.',
      email: isCommander ? 'commander@ibvap.mil' : 'operator@ibvap.mil',
      clearanceLevel: isCommander ? 'TOP-SECRET // LEVEL-4' : 'SECRET-TACTICAL // LEVEL-2',
    });
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        login,
        logout,
        switchRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const ProtectedRoute: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};
