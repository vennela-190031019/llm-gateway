import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AuthProvider } from "./hooks/useAuth";
import { ComingSoon } from "./pages/ComingSoon";
import { Dashboard } from "./pages/Dashboard";
import { Login } from "./pages/Login";
import { Models } from "./pages/Models";
import { RequestDetail } from "./pages/RequestDetail";
import { Requests } from "./pages/Requests";

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
                <Route path="/costs" element={<ComingSoon title="Costs" />} />
                <Route path="/prompts" element={<ComingSoon title="Prompts" />} />
                <Route path="/evaluations" element={<ComingSoon title="Evaluations" />} />
                <Route path="/system-health" element={<ComingSoon title="System Health" />} />
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
