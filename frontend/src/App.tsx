import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { LiveEventsProvider } from "./hooks/LiveEvents";
import { UiSettingsProvider } from "./hooks/UiSettings";
import { MonitoringProvider } from "./hooks/Monitoring";
import Dashboard from "./pages/Dashboard";
import Slots from "./pages/Slots";
import SteamDota from "./pages/SteamDota";
import SystemPage from "./pages/System";
import Logs from "./pages/Logs";
import SettingsPage from "./pages/Settings";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/system" element={<SystemPage />} />
      <Route path="/steam" element={<SteamDota />} />
      <Route path="/slots" element={<Slots />} />
      <Route path="/logs" element={<Logs />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="*" element={<div className="text-gray-400">Страница не найдена.</div>} />
    </Routes>
  );
}

export default function App() {
  return (
    <LiveEventsProvider>
      <UiSettingsProvider>
        <MonitoringProvider>
          <Layout>
            <AppRoutes />
          </Layout>
        </MonitoringProvider>
      </UiSettingsProvider>
    </LiveEventsProvider>
  );
}
