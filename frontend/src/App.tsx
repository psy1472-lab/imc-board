import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { DashboardFilterProvider } from "./context/DashboardFilterContext";
import { AdminAuthProvider } from "./context/AdminAuthContext";
import { ThemeProvider } from "./context/ThemeContext";
import { AdminRoute } from "./components/auth/AdminRoute";
import { DashboardLayout } from "./layouts/DashboardLayout";
import ReportsPage from "./pages/ReportsPage";
import SettingsPage from "./pages/SettingsPage";
import BriefingPage from "./pages/BriefingPage";
import SafetyAnalysisPage from "./pages/SafetyAnalysisPage";
import EquipmentAnalysisPage from "./pages/EquipmentAnalysisPage";
import TransportAnalysisPage from "./pages/TransportAnalysisPage";
import StaffingAnalysisPage from "./pages/StaffingAnalysisPage";
import SummaryDashboard from "./pages/SummaryDashboard";
import VolumeAnalysisPage from "./pages/VolumeAnalysisPage";
import "./index.css";

export default function App() {
  return (
    <ThemeProvider>
      <AdminAuthProvider>
        <DashboardFilterProvider>
          <BrowserRouter>
            <Routes>
              <Route element={<DashboardLayout />}>
                <Route index element={<SummaryDashboard />} />
                <Route path="volume" element={<VolumeAnalysisPage />} />
                <Route path="staffing" element={<StaffingAnalysisPage />} />
                <Route path="transport" element={<TransportAnalysisPage />} />
                <Route path="equipment" element={<EquipmentAnalysisPage />} />
                <Route path="safety" element={<SafetyAnalysisPage />} />
                <Route path="briefing" element={<BriefingPage />} />
                <Route
                  path="reports"
                  element={
                    <AdminRoute title="보고서·다운로드" description="PDF 업로드, 보고서 목록, 데이터 다운로드는 관리자만 이용할 수 있습니다.">
                      <ReportsPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="settings"
                  element={
                    <AdminRoute title="시스템 관리" description="시스템 상태와 임계값 설정은 관리자만 이용할 수 있습니다.">
                      <SettingsPage />
                    </AdminRoute>
                  }
                />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </DashboardFilterProvider>
      </AdminAuthProvider>
    </ThemeProvider>
  );
}
