import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Toaster } from "react-hot-toast";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { TopProgress } from "./components/TopProgress";
import "@fontsource-variable/inter/index.css";
import "@fontsource-variable/plus-jakarta-sans/wght.css";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    // Show what we already have straight away and refresh it quietly in the background.
    queries: { retry: 1, staleTime: 30_000, gcTime: 10 * 60_000, refetchOnWindowFocus: true },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <App />
          <TopProgress />
          <Toaster position="top-right" toastOptions={{ duration: 4000, style: { fontSize: "14px", borderRadius: "14px", boxShadow: "0 12px 32px -12px rgba(16,24,40,.25)" } }} />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
