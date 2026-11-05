import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { LiveEventsProvider } from "./hooks/LiveEvents";
import { MetaProvider } from "./hooks/MetaContext";
import { UiSettingsProvider } from "./hooks/UiSettings";
import Analytics from "./pages/Analytics";
import BotConfig from "./pages/BotConfig";
import Dashboard from "./pages/Dashboard";
import History from "./pages/History";
import LiveMatch from "./pages/LiveMatch";
import Logs from "./pages/Logs";
import MatchControl from "./pages/MatchControl";
import Players from "./pages/Players";
import SettingsPage from "./pages/Settings";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/players" element={<Players />} />
      <Route path="/bots" element={<BotConfig />} />
      <Route path="/match-control" element={<MatchControl />} />
      <Route path="/live" element={<LiveMatch />} />
      <Route path="/live/:sessionId" element={<LiveMatch />} />
      <Route path="/analytics" element={<Analytics />} />
      <Route path="/history" element={<History />} />
      <Route path="/logs" element={<Logs />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="*" element={<div className="text-gray-400">Page not found.</div>} />
    </Routes>
  );
}

export default function App() {
  return (
    <LiveEventsProvider>
      <MetaProvider>
        <UiSettingsProvider>
          <Layout>
            <AppRoutes />
          </Layout>
        </UiSettingsProvider>
      </MetaProvider>
    </LiveEventsProvider>
  );
}
