import type { QueryClient } from "@tanstack/react-query";
import { applicationsApi, dashboardApi, jobsApi, profileApi } from "../api/endpoints";
import type { Role } from "../api/types";

/**
 * Makes clicks feel instant: the data (and code) of the page behind a link is fetched as soon as the pointer
 * rests on the link, so by the time the click happens it is usually already there.
 */

export const loadCandidateDetail = () => import("../pages/recruiter/CandidateDetail");
export const loadInterview = () => import("../pages/candidate/Interview");
export const loadJobDashboard = () => import("../pages/recruiter/JobDashboard");
export const loadCandidateProfile = () => import("../pages/recruiter/CandidateProfile");

const STALE = 30_000;

export function prefetchPath(qc: QueryClient, path: string) {
  const [, a, b, c] = path.split("/");
  const q = (queryKey: unknown[], queryFn: () => Promise<unknown>) => qc.prefetchQuery({ queryKey, queryFn, staleTime: STALE });
  if (a === "recruiter" && (!b || (b === "jobs" && !c))) q(["overview"], dashboardApi.overview);
  else if (a === "recruiter" && b === "jobs" && c && c !== "new") {
    loadJobDashboard();
    q(["job", c], () => jobsApi.get(c));
    q(["stats", c], () => jobsApi.stats(c));
  } else if (a === "recruiter" && b === "applications" && c) {
    loadCandidateDetail(); // code only: opening the details marks the candidate as seen, so wait for the click
  } else if (a === "jobs" && !b) q(["jobs", "browse", ""], () => jobsApi.list(""));
  else if (a === "jobs" && b) q(["job", b], () => jobsApi.get(b));
  else if (a === "applications") q(["applications", "mine"], applicationsApi.mine);
  else if (a === "profile") q(["profile", "me"], profileApi.me);
  else if (a === "interview") {
    loadInterview();
    import("../components/useFaceTracker")
      .then((m) => m.loadFaceLandmarker())
      .then(() => import("../components/useObjectWatch"))
      .then((m) => m.loadObjectDetector())
      .catch(() => undefined);
  }
}

/** After login, quietly load the main pages of this portal in the background. */
export function warmUp(qc: QueryClient, role: Role) {
  const idle = (fn: () => void) =>
    typeof window.requestIdleCallback === "function" ? window.requestIdleCallback(fn, { timeout: 2000 }) : setTimeout(fn, 300);
  idle(() => {
    if (role === "recruiter") {
      prefetchPath(qc, "/recruiter");
      loadJobDashboard();
      loadCandidateDetail();
    } else {
      ["/jobs", "/applications", "/profile"].forEach((p) => prefetchPath(qc, p));
    }
  });
}

/** Props for a link: prefetch on hover, keyboard focus or touch. */
export function prefetchProps(qc: QueryClient, path: string) {
  const go = () => prefetchPath(qc, path);
  return { onMouseEnter: go, onFocus: go, onTouchStart: go };
}
