import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, ProtectedRoute } from '@/components/auth/AuthProvider';
import { AlertProvider } from '@/components/alerts/AlertProvider';
import { AppLayout } from '@/components/layout/AppLayout';
import { LoginPage } from '@/pages/LoginPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { LiveFeedsPage } from '@/pages/LiveFeedsPage';
import { IncidentsPage } from '@/pages/IncidentsPage';
import { ZonesPage } from '@/pages/ZonesPage';
import { WatchlistPage } from '@/pages/WatchlistPage';
import { AnalyticsPage } from '@/pages/AnalyticsPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { DesignShowcasePage } from '@/pages/DesignShowcasePage';

export const AppRouter = () => {
  return (
    <AuthProvider>
      <AlertProvider>
        <BrowserRouter>
          <Routes>
            {/* Public Gateway Login */}
            <Route path="/login" element={<LoginPage />} />

            {/* Protected Command Center Operations */}
            <Route
              element={
                <ProtectedRoute>
                  <AppLayout />
                </ProtectedRoute>
              }
            >
              <Route path="/" element={<DashboardPage />} />
              <Route path="/live" element={<LiveFeedsPage />} />
              <Route path="/incidents" element={<IncidentsPage />} />
              <Route path="/zones" element={<ZonesPage />} />
              <Route path="/watchlist" element={<WatchlistPage />} />
              <Route path="/analytics" element={<AnalyticsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/design-system" element={<DesignShowcasePage />} />
            </Route>

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AlertProvider>
    </AuthProvider>
  );
};
