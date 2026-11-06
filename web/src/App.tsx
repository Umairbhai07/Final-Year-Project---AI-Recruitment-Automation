import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { GuestOnly, ProtectedRoute } from "./auth/ProtectedRoute";
import { loadCandidateDetail, loadCandidateProfile, loadInterview, loadJobDashboard } from "./lib/prefetch";
import {
  CandidateLayout,
  FocusLayout,
  PublicLayout,
  RecruiterLayout,
} from "./components/Layout";
import Landing from "./pages/Landing";
import NotFound from "./pages/NotFound";
import Login from "./pages/auth/Login";
import ForgotPassword from "./pages/auth/ForgotPassword";
import Register from "./pages/auth/Register";
import ResetPassword from "./pages/auth/ResetPassword";
import BrowseJobs from "./pages/candidate/BrowseJobs";
import JobDetail from "./pages/candidate/JobDetail";
import MyApplications from "./pages/candidate/MyApplications";
import Profile from "./pages/candidate/Profile";
import VerifyEmail from "./pages/auth/VerifyEmail";
import JobForm from "./pages/recruiter/JobForm";
import Overview from "./pages/recruiter/Overview";

// Pages with heavy libraries (charts, face tracking) load only when opened.
const CandidateDetail = lazy(loadCandidateDetail);
const Interview = lazy(loadInterview);
const JobDashboard = lazy(loadJobDashboard);
const CandidateProfile = lazy(loadCandidateProfile);
const CandidateReport = lazy(() => import("./pages/recruiter/CandidateReport"));

export default function App() {
  return (
    <Suspense
      fallback={
        <div className="p-8 text-center text-sm text-slate-500">Loading…</div>
      }
    >
      <Routes>
        <Route element={<GuestOnly />}>
          <Route element={<PublicLayout />}>
            <Route path="/" element={<Landing />} />
          </Route>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
        </Route>

        <Route path="/verify-email" element={<VerifyEmail />} />

        <Route element={<ProtectedRoute role="recruiter" />}>
          <Route element={<RecruiterLayout />}>
            <Route path="/recruiter" element={<Overview />} />
            <Route path="/recruiter/jobs" element={<Navigate to="/recruiter" replace />} />
            <Route path="/recruiter/jobs/new" element={<JobForm />} />
            <Route path="/recruiter/jobs/:id" element={<JobDashboard />} />
            <Route path="/recruiter/jobs/:id/edit" element={<JobForm />} />
            <Route path="/recruiter/applications/:id" element={<CandidateDetail />} />
            <Route path="/recruiter/candidates/:candidateId" element={<CandidateProfile />} />
          </Route>
        </Route>

        <Route element={<ProtectedRoute role="recruiter" />}>
          <Route path="/recruiter/applications/:id/report" element={<CandidateReport />} />
        </Route>

        <Route element={<ProtectedRoute role="candidate" />}>
          <Route element={<CandidateLayout />}>
            <Route path="/jobs" element={<BrowseJobs />} />
            <Route path="/jobs/:id" element={<JobDetail />} />
            <Route path="/applications" element={<MyApplications />} />
            <Route path="/profile" element={<Profile />} />
          </Route>
          <Route element={<FocusLayout />}>
            <Route path="/interview/:sessionId" element={<Interview />} />
          </Route>
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
