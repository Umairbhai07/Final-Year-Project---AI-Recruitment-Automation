import { Navigate, Outlet, useLocation } from "react-router-dom";
import type { Role } from "../api/types";
import { FullPageSpinner } from "../components/ui";
import { useAuth } from "./AuthContext";

export function homeFor(role: Role) {
  return role === "recruiter" ? "/recruiter" : "/jobs";
}

/** Only logged-in users with the given role may see the nested routes. */
export function ProtectedRoute({ role }: { role?: Role }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <FullPageSpinner />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (role && user.role !== role) return <Navigate to={homeFor(user.role)} replace />;
  return <Outlet />;
}

/** Login/register pages: send already logged-in users to their home page. */
export function GuestOnly() {
  const { user, loading } = useAuth();
  if (loading) return <FullPageSpinner />;
  if (user) return <Navigate to={homeFor(user.role)} replace />;
  return <Outlet />;
}
