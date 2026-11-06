import { api, deviceTokens } from "./client";
import type {
  ApplyResult,
  AnswerResult,
  ApplicationDetail,
  CandidateFilters,
  CandidateRow,
  CandidateView,
  Decision,
  Eligibility,
  EventsResult,
  IntegrityEventType,
  InterviewState,
  Job,
  JobInput,
  JobStats,
  JobStatus,
  MyApplication,
  MyJob,
  Overview,
  Profile,
  ProfileInput,
  Role,
  SnapshotReason,
  TokenResponse,
  User,
} from "./types";

const data = <T>(p: Promise<{ data: T }>) => p.then((r) => r.data);

export const authApi = {
  register: (body: { full_name: string; email: string; password: string; role: Role }) =>
    data<User>(api.post("/auth/register", body)),
  login: (email: string, password: string, role?: Role) =>
    data<TokenResponse>(api.post("/auth/login", { email, password, role })),
  logout: (refresh_token: string) => api.post("/auth/logout", { refresh_token }),
  me: () => data<User>(api.get("/auth/me")),
  forgotPassword: (email: string) => api.post("/auth/forgot-password", { email }),
  resetPassword: (token: string, password: string) => api.post("/auth/reset-password", { token, password }),
  resetWithCode: (email: string, code: string, password: string) =>
    api.post("/auth/reset-password-code", { email, code, password }),
  sendChangeCode: (current_password: string) => api.post("/auth/change-password/send-code", { current_password }),
  changePassword: (code: string, new_password: string) => api.post("/auth/change-password", { code, new_password }),
  verifyEmail: (token: string) => data<User>(api.post("/auth/verify-email", { token })),
  resendVerification: () => api.post("/auth/resend-verification"),
};

export const profileApi = {
  me: () => data<Profile>(api.get("/profile/me")),
  save: (body: ProfileInput) => data<Profile>(api.put("/profile/me", body)),
  uploadPhoto: (image: Blob) => {
    const form = new FormData();
    form.append("image", image, "photo.jpg");
    return data<Profile>(api.post("/profile/me/photo", form));
  },
  uploadResume: (file: File) => {
    const form = new FormData();
    form.append("resume", file);
    return data<Profile>(api.post("/profile/me/resume", form));
  },
  eligibility: (jobId: string) => data<Eligibility>(api.get(`/jobs/${jobId}/eligibility`)),
  candidate: (candidateId: string) => data<CandidateView>(api.get(`/candidates/${candidateId}`)),
};

export const dashboardApi = {
  overview: () => data<Overview>(api.get("/dashboard/overview")),
};

export const jobsApi = {
  list: (q?: string) => data<Job[]>(api.get("/jobs", { params: q ? { q } : {} })),
  mine: () => data<MyJob[]>(api.get("/jobs/mine")),
  get: (id: string) => data<Job>(api.get(`/jobs/${id}`)),
  create: (body: JobInput) => data<Job>(api.post("/jobs", body)),
  update: (id: string, body: Partial<JobInput>) => data<Job>(api.patch(`/jobs/${id}`, body)),
  setStatus: (id: string, status: JobStatus) => data<Job>(api.patch(`/jobs/${id}/status`, { status })),
  candidates: (id: string, filters: CandidateFilters) => {
    const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== "" && v !== undefined));
    return data<CandidateRow[]>(api.get(`/jobs/${id}/candidates`, { params }));
  },
  stats: (id: string) => data<JobStats>(api.get(`/jobs/${id}/stats`)),
};

export const applicationsApi = {
  /** Applies with the profile's resume, or with `file` for this job only. */
  apply: (jobId: string, file: File | null, answers: Record<string, string>, onProgress?: (pct: number) => void) => {
    const form = new FormData();
    if (file) form.append("resume", file);
    form.append("answers", JSON.stringify(answers));
    return data<ApplyResult>(
      api.post(`/jobs/${jobId}/apply`, form, {
        onUploadProgress: (e) => e.total && onProgress?.(Math.round((e.loaded / e.total) * 100)),
      }),
    );
  },
  mine: () => data<MyApplication[]>(api.get("/applications/mine")),
  detail: (id: string) => data<ApplicationDetail>(api.get(`/applications/${id}/detail`)),
  decide: (id: string, decision: Decision, notes: string | null) =>
    data<ApplicationDetail>(api.patch(`/applications/${id}/decision`, { decision, notes })),
  rescreen: (id: string) => api.post(`/applications/${id}/rescreen`),
  invite: (id: string) => data<ApplicationDetail>(api.post(`/applications/${id}/invite`)),
  releaseDevice: (id: string) => data<ApplicationDetail>(api.post(`/applications/${id}/interview/release-device`)),
};

export const interviewsApi = {
  get: (id: string) => data<InterviewState>(api.get(`/interviews/${id}`)),
  start: async (id: string) => {
    const s = await data<InterviewState>(api.post(`/interviews/${id}/start`));
    if (s.device_token) deviceTokens.set(id, s.device_token); // this browser is now the interview's device
    return s;
  },
  answer: (id: string, questionIndex: number, audio: Blob, filename: string, attention?: number | null) => {
    const form = new FormData();
    form.append("question_index", String(questionIndex));
    form.append("audio", audio, filename);
    if (attention !== null && attention !== undefined) form.append("attention", attention.toFixed(1));
    return data<AnswerResult>(api.post(`/interviews/${id}/answer`, form, { timeout: 90_000 }));
  },
  reportIssue: (id: string, text: string) => api.post(`/interviews/${id}/report-issue`, { text }),
  skip: (id: string, questionIndex: number) =>
    data<AnswerResult>(api.post(`/interviews/${id}/skip`, { question_index: questionIndex })),
  events: (id: string, events: { type: IntegrityEventType; question_index?: number | null; detail?: string; value?: number }[]) =>
    data<EventsResult>(api.post(`/interviews/${id}/events`, { events })),
  snapshot: (id: string, image: Blob, reason: SnapshotReason, questionIndex: number | null) => {
    const form = new FormData();
    form.append("image", image, "snapshot.jpg");
    form.append("reason", reason);
    if (questionIndex !== null) form.append("question_index", String(questionIndex));
    return data<{ stored: boolean; count: number }>(api.post(`/interviews/${id}/snapshot`, form));
  },
};
