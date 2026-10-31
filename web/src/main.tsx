import { MotionConfig } from "motion/react";
import { LoaderCircle } from "lucide-react";
import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ToastProvider } from "./components/ui";
import { I18nProvider } from "./i18n";
import "./index.css";
import Home from "./pages/Home";

const Schemes = lazy(() => import("./pages/Schemes"));
const Engine = lazy(() => import("./pages/Engine"));
const Grievance = lazy(() => import("./pages/Grievance"));
const Board = lazy(() => import("./pages/Board"));
const Admin = lazy(() => import("./pages/Admin"));
const AgentHome = lazy(() => import("./pages/AgentHome"));
const AgentRoom = lazy(() => import("./pages/AgentRoom"));
const AgentHistory = lazy(() => import("./pages/AgentHistory"));
const AgentRun = lazy(() => import("./pages/AgentRun"));

function Fallback() {
  return <div className="grid min-h-[50vh] place-items-center"><LoaderCircle className="size-8 animate-spin text-saffron-500" aria-label="Loading" /></div>;
}

function App() {
  const { pathname } = useLocation();
  const dark = pathname.startsWith("/agent") || pathname.startsWith("/citizen");
  return (
    <Layout dark={dark}>
      <Suspense fallback={<Fallback />}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/schemes" element={<Schemes />} />
          <Route path="/schemes/engine" element={<Engine />} />
          <Route path="/grievance" element={<Grievance />} />
          <Route path="/board" element={<Board />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="/admin/queue" element={<Admin />} />
          <Route path="/agent" element={<AgentHome />} />
          <Route path="/agent/history" element={<AgentHistory />} />
          <Route path="/agent/runs/:runId" element={<AgentRun />} />
          <Route path="/citizen/:taskId" element={<AgentRoom />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </Layout>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MotionConfig reducedMotion="user">
      <I18nProvider>
        <ToastProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </ToastProvider>
      </I18nProvider>
    </MotionConfig>
  </StrictMode>,
);
