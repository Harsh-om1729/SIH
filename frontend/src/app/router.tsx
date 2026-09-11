import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from '@/components/auth/AuthProvider';
import { AlertProvider } from '@/components/alerts/AlertProvider';
import { SystemHealthProvider } from '@/components/system/SystemHealthProvider';
import { AppLayout } from '@/components/layout/AppLayout';
import { DashboardPage } from '@/pages/DashboardPage';
import { LiveFeedsPage } from '@/pages/LiveFeedsPage';
import { IncidentsPage } from '@/pages/IncidentsPage';
import { ZonesPage } from '@/pages/ZonesPage';
import { AnalyticsPage } from '@/pages/AnalyticsPage';
import { WatchlistPage } from '@/pages/WatchlistPage';
import { SettingsPage } from '@/pages/SettingsPage';

export const AppRouter = () => {
  return (
    <AuthProvider>
      <SystemHealthProvider>
        <AlertProvider>
          <BrowserRouter>
            <Routes>
              {/* Command Center Operations */}
              <Route element={<AppLayout />}>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/live" element={<LiveFeedsPage />} />
                <Route path="/detections" element={<IncidentsPage />} />
                <Route path="/incidents" element={<IncidentsPage />} />
                <Route path="/zones" element={<ZonesPage />} />
                <Route path="/analytics" element={<AnalyticsPage />} />
                {/* Both pages existed and were wired to the backend but had no
                    route — /watchlist even redirected away — so enrolment
                    and system health were unreachable from the UI. */}
                <Route path="/watchlist" element={<WatchlistPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Route>

              {/* Login is a role selector, not authentication (see AuthProvider):
                  every visitor is already signed in, so the page has no job. */}
              <Route path="/login" element={<Navigate to="/" replace />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </AlertProvider>
      </SystemHealthProvider>
    </AuthProvider>
  );
};
