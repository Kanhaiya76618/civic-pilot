import { MotionConfig } from "motion/react";
import { LoaderCircle } from "lucide-react";
import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { getAuthSession } from "./auth";
import { Layout } from "./components/Layout";
import { ToastProvider } from "./components/ui";
import { I18nProvider } from "./i18n";
import "./index.css";
import Landing from "./pages/Landing";

const Schemes = lazy(() => import("./pages/Schemes"));
const Engine = lazy(() => import("./pages/Engine"));
const Grievance = lazy(() => import("./pages/Grievance"));
const Board = lazy(() => import("./pages/Board"));
const Admin = lazy(() => import("./pages/Admin"));
const AgentHome = lazy(() => import("./pages/AgentHome"));
const AgentRoom = lazy(() => import("./pages/AgentRoom"));
const AgentHistory = lazy(() => import("./pages/AgentHistory"));
const AgentRun = lazy(() => import("./pages/AgentRun"));
const CitizenHome = lazy(() => import("./pages/CitizenHome"));
const MyHistory = lazy(() => import("./pages/MyHistory"));
const SignIn = lazy(() => import("./pages/SignIn"));

function Fallback() {
  return <div className="grid min-h-[50vh] place-items-center"><LoaderCircle className="size-8 animate-spin text-saffron-500" aria-label="Loading" /></div>;
}

function RequireAuth() {
  const session = getAuthSession();
  const location = useLocation();
  if (!session) {
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/signin?next=${encodeURIComponent(next)}`} replace />;
  }
  return <Outlet />;
}

function RequireAdmin() {
  const session = getAuthSession();
  if (!session) return <Navigate to="/signin?role=admin&next=%2Fadmin" replace />;
  return session.user.role === "admin" ? <Outlet /> : <Navigate to="/home" replace />;
}

function App() {
  const { pathname } = useLocation();
  const dark = pathname.startsWith("/agent") || pathname.startsWith("/citizen");
  return (
    <Layout dark={dark}>
      <Suspense fallback={<Fallback />}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/signin" element={<SignIn />} />
          <Route path="/board" element={<Board />} />  {/* public: "open to everyone, no login" */}
          <Route element={<RequireAuth />}>
            <Route path="/home" element={<CitizenHome />} />
            <Route path="/history" element={<MyHistory />} />
            <Route path="/schemes" element={<Schemes />} />
            <Route path="/schemes/engine" element={<Engine />} />
            <Route path="/grievance" element={<Grievance />} />
            <Route path="/agent" element={<AgentHome />} />
            <Route path="/agent/history" element={<AgentHistory />} />
            <Route path="/agent/runs/:runId" element={<AgentRun />} />
            <Route path="/citizen/:taskId" element={<AgentRoom />} />
          </Route>
          <Route element={<RequireAdmin />}>
            <Route path="/admin" element={<Admin />} />
            <Route path="/admin/queue" element={<Admin />} />
          </Route>
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
