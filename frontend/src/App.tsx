import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AuthProvider } from "./hooks/useAuth";
import { Costs } from "./pages/Costs";
import { Dashboard } from "./pages/Dashboard";
import { Evaluations } from "./pages/Evaluations";
import { Login } from "./pages/Login";
import { Models } from "./pages/Models";
import { Prompts } from "./pages/Prompts";
import { RequestDetail } from "./pages/RequestDetail";
import { Requests } from "./pages/Requests";
import { SystemHealth } from "./pages/SystemHealth";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <Layout>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/models" element={<Models />} />
                <Route path="/requests" element={<Requests />} />
                <Route path="/requests/:requestId" element={<RequestDetail />} />
                <Route path="/costs" element={<Costs />} />
                <Route path="/prompts" element={<Prompts />} />
                <Route path="/evaluations" element={<Evaluations />} />
                <Route path="/system-health" element={<SystemHealth />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Layout>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
