import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from '@/components/auth/AuthProvider';
import { AlertProvider } from '@/components/alerts/AlertProvider';
import { AppLayout } from '@/components/layout/AppLayout';
import { DashboardPage } from '@/pages/DashboardPage';
import { LiveFeedsPage } from '@/pages/LiveFeedsPage';
import { IncidentsPage } from '@/pages/IncidentsPage';
import { ZonesPage } from '@/pages/ZonesPage';
import { AnalyticsPage } from '@/pages/AnalyticsPage';

export const AppRouter = () => {
  return (
    <AuthProvider>
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
            </Route>

            {/* Redirect legacy /login, /watchlist and all unmatched routes */}
            <Route path="/login" element={<Navigate to="/" replace />} />
            <Route path="/watchlist" element={<Navigate to="/detections" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AlertProvider>
    </AuthProvider>
  );
};
