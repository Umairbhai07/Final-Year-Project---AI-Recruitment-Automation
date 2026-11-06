export type Role = "recruiter" | "candidate";
export type JobStatus = "active" | "paused" | "closed";
export type EducationLevel = "none" | "matric" | "high_school" | "diploma" | "bachelors" | "masters" | "phd";
export type Stage =
  | "submitted"
  | "under_review"
  | "screening_failed"
  | "not_qualified"
  | "interview_invited"
  | "interview_in_progress"
  | "evaluated";
export type Decision = "pending" | "shortlisted" | "rejected";

export interface User {
  id: string;
  full_name: string;
  email: string;
  role: Role;
  created_at: string;
  email_verified?: boolean;
  /** Email confirmation is switched on and this account has not confirmed yet. */
  must_verify?: boolean;
  /** Candidates: the profile photo, shown in the account menu. */
  photo_url?: string | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  user: User;
}

export type QuestionType = "text" | "long_text" | "number" | "select" | "yes_no" | "url";

export interface FormQuestion {
  id: string;
  label: string;
  type: QuestionType;
  required: boolean;
  options?: string[];
  help?: string | null;
  min?: number | null;
  max?: number | null;
  /** Must-have rules (recruiters only see these): passing answers, or the passing number range. */
  accept?: string[];
  must_min?: number | null;
  must_max?: number | null;
}

export interface FormAnswer {
  id: string;
  label: string;
  answer: string;
}

export interface JobInput {
  title: string;
  description: string;
  required_skills: string[];
  min_experience_years: number;
  education_level: EducationLevel;
  min_cgpa: number | null;
  deadline: string | null;
  screening_threshold: number;
  num_questions: number;
  seconds_per_question: number;
  think_seconds: number;
  follow_up_questions: number;
  require_webcam: boolean;
  application_form: FormQuestion[];
}

export interface Job extends JobInput {
  id: string;
  recruiter_id: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
  company: string | null;
  has_applied: boolean | null;
  /** Candidates only: does their profile meet this job's minimum requirements? */
  eligibility?: Eligibility | null;
  /** Recruiters only: candidates stopped by the minimum requirements. */
  blocked_applications?: number | null;
}

export interface RequirementCheck {
  rule: "education" | "experience" | "cgpa";
  label: string;
  required: string;
  yours: string;
  ok: boolean;
}

export interface Eligibility {
  eligible: boolean;
  profile_complete: boolean;
  checks: RequirementCheck[];
}

export interface ExperienceItem {
  title: string;
  company: string;
  years: number;
  description?: string | null;
}

export interface Profile {
  user_id: string;
  full_name: string;
  email: string;
  headline: string | null;
  phone: string | null;
  city: string | null;
  about: string | null;
  photo_url: string | null;
  highest_degree: EducationLevel | null;
  highest_degree_label: string | null;
  field_of_study: string | null;
  institute: string | null;
  cgpa: number | null;
  graduation_year: number | null;
  experience_years: number | null;
  experience: ExperienceItem[];
  skills: string[];
  linkedin_url: string | null;
  github_url: string | null;
  portfolio_url: string | null;
  resume_filename: string | null;
  has_resume: boolean;
  completion: number;
  missing: string[];
  complete: boolean;
}

export type ProfileInput = Partial<Omit<Profile, "user_id" | "email" | "photo_url" | "highest_degree_label" | "resume_filename" | "has_resume" | "completion" | "missing" | "complete">>;

export interface CandidateHistoryItem {
  application_id: string;
  job_id: string;
  job_title: string;
  job_status: JobStatus;
  applied_at: string;
  stage: Stage;
  decision: Decision;
  composite_score: number | null;
  incomplete: boolean;
  last_activity: string | null;
  last_activity_at: string | null;
  mismatches: string[];
}

export interface CandidateView {
  profile: Omit<Profile, "missing">;
  member_since: string;
  applications: CandidateHistoryItem[];
}

export interface MyJob extends Job {
  applicant_count: number;
  evaluated_count: number;
  avg_score: number | null;
}

export interface MyApplication {
  id: string;
  job_id: string;
  job_title: string;
  job_status: JobStatus;
  status_label: string;
  stage_step: number;
  applied_at: string;
  updated_at: string;
  interview_session_id: string | null;
  interview_status: string | null;
  can_start_interview: boolean;
  shortlisted: boolean;
  /** Why it was not selected (a missed requirement, someone else's resume, ...). */
  reason?: string | null;
}

export interface ApplyResult {
  id: string;
  stage: string;
  status_label: string;
  reason: string | null;
}

export interface CandidateRow {
  rank: number;
  application_id: string;
  candidate_id: string;
  full_name: string;
  email: string;
  photo_url: string | null;
  headline: string | null;
  city: string | null;
  degree: string | null;
  experience_years: number | null;
  cgpa: number | null;
  mismatch_count: number;
  stage: Stage;
  decision: Decision;
  composite_score: number | null;
  skill_score: number | null;
  experience_score: number | null;
  education_score: number | null;
  resume_total: number | null;
  interview_score: number | null;
  incomplete: boolean;
  needs_manual_review: boolean;
  issue_reported: boolean;
  integrity_level: IntegrityLevel | null;
  interview_completed_at: string | null;
  last_activity_at: string | null;
  last_activity: string | null;
  /** Something happened since the recruiter last opened this candidate. */
  is_new: boolean;
  archived: boolean;
  form_answers: FormAnswer[];
  applied_at: string;
}

export interface JobStats {
  job_id: string;
  total: number;
  by_stage: Record<Stage, number>;
  by_decision: Record<Decision, number>;
  screened: number;
  interviewed: number;
  evaluated: number;
  avg_composite: number | null;
  avg_resume: number | null;
  histogram: { range: string; count: number }[];
  funnel: FunnelStep[];
  missing_skills: { skill: string; count: number }[];
  breakdown: { part: string; percent: number | null }[];
  integrity: { clean: number; warning: number; high: number };
  degrees: { label: string; count: number }[];
  blocked_applications: number;
  mismatches: number;
}

export interface FunnelStep {
  key: "blocked" | "applied" | "qualified" | "interviewed" | "shortlisted";
  label: string;
  count: number;
}

export interface InterviewResponse {
  question_index: number;
  question: string;
  focus: string;
  transcript: string | null;
  accuracy: number;
  relevance: number;
  clarity: number;
  score: number;
  feedback: string | null;
  has_audio: boolean;
  kind: QuestionKind;
  /** The AI was busy; this answer is scored later. */
  pending?: boolean;
}

export interface ApplicationDetail {
  id: string;
  job_id: string;
  job_title: string;
  required_skills: string[];
  candidate: {
    id: string;
    full_name: string;
    email: string;
    photo_url: string | null;
    headline: string | null;
    phone: string | null;
    city: string | null;
    linkedin_url: string | null;
    github_url: string | null;
    portfolio_url: string | null;
  };
  profile_snapshot: (Partial<Profile> & { highest_degree_label?: string }) | null;
  mismatches: string[];
  requirements: RequirementCheck[];
  stage: Stage;
  decision: Decision;
  notes: string | null;
  needs_manual_review: boolean;
  review_reason: string | null;
  archived: boolean;
  form_answers: FormAnswer[];
  applied_at: string;
  resume_filename: string | null;
  parsed_resume: {
    education_level?: EducationLevel;
    skills: string[];
    matched_skills: string[];
    missing_skills: string[];
    years_experience: number;
    education: string;
    certifications: string[];
    summary: string;
  } | null;
  scores: {
    skill_score: number;
    experience_score: number;
    education_score: number;
    resume_total: number;
    interview_score: number | null;
    composite_score: number;
    resume_reasoning: string | null;
    incomplete: boolean;
  } | null;
  interview: {
    session_id: string;
    status: string;
    total_questions: number;
    current_index: number;
    invited_at: string;
    started_at: string | null;
    completed_at: string | null;
    issue_reported: boolean;
    issue_text: string | null;
    questions: { index: number; text: string; focus: string; kind?: QuestionKind; parent_index?: number }[];
    responses: InterviewResponse[];
    integrity: IntegrityReport | null;
    device_locked: boolean;
  } | null;
}

export type IntegrityLevel = "clean" | "warning" | "high";

export interface IntegrityEvent {
  type: string;
  label: string;
  at: string;
  question_index: number | null;
  detail: string | null;
  strike: boolean;
}

export interface IntegrityReport {
  level: IntegrityLevel;
  strikes: number;
  max_strikes: number;
  terminated: boolean;
  terminated_reason: string | null;
  counts: { type: string; label: string; count: number }[];
  events: IntegrityEvent[];
  /** Share of each answer spent looking at the screen (webcam), in percent. */
  attention: { average: number; per_question: { question_index: number; percent: number }[] } | null;
  webcam_used: boolean;
  snapshots: { index: number; at: string; reason: string; question_index: number | null; label: string }[];
}

export interface InterviewState {
  session_id: string;
  device_locked: boolean;
  /** Only in the reply to the first start: this browser's key for the rest of the interview. */
  device_token?: string | null;
  job_title: string;
  status: "invited" | "in_progress" | "completed";
  total_questions: number;
  current_index: number;
  current_question: string | null;
  current_kind: QuestionKind | null;
  seconds_per_question: number;
  think_seconds: number;
  /** Seconds left for the current question (hearing + thinking + answering), counted by the server. */
  seconds_left: number | null;
  follow_ups_planned: number;
  strikes: number;
  max_strikes: number;
  terminated: boolean;
  can_answer: boolean;
  require_webcam: boolean;
}

export type QuestionKind = "main" | "follow_up";

export interface AnswerResult {
  completed: boolean;
  next_index: number | null;
  next_question: string | null;
  next_kind: QuestionKind | null;
  total_questions: number;
  seconds_left: number | null;
}

/** Lockdown events the browser reports. Leaving the window (first five) and turning the camera off count as strikes. */
export type IntegrityEventType =
  | "fullscreen_exit" | "tab_hidden" | "window_blur" | "page_reload" | "multiple_tabs"
  | "copy_attempt" | "paste_attempt" | "context_menu" | "devtools_key" | "blocked_key" | "screenshot_key"
  | "second_screen" | "question_repeated" | "tts_unavailable" | "keyboard_lock_unavailable"
  | "camera_off" | "no_face" | "multiple_faces" | "looking_away" | "eyes_away" | "attention"
  | "phone_detected" | "book_detected" | "screen_detected" | "object_detection_unavailable";

export type SnapshotReason =
  | "start" | "random" | "no_face" | "multiple_faces" | "looking_away" | "eyes_away"
  | "phone_detected" | "book_detected" | "screen_detected";

export interface EventsResult {
  strikes: number;
  max_strikes: number;
  terminated: boolean;
}

export interface CandidateFilters {
  min_score?: number;
  max_score?: number;
  stage?: Stage | "";
  decision?: Decision | "";
  sort?: "recent" | "composite" | "resume" | "interview" | "date" | "name";
}

export interface OverviewApp {
  application_id: string;
  job_id: string;
  job_title: string;
  full_name: string;
  stage: Stage;
  decision: Decision;
  composite_score: number | null;
  incomplete: boolean;
  applied_at: string;
  reason?: string | null;
  last_activity_at: string | null;
  last_activity: string | null;
  is_new: boolean;
  integrity_level: IntegrityLevel | null;
}

export interface OverviewJob {
  id: string;
  title: string;
  status: JobStatus;
  created_at: string;
  deadline: string | null;
  required_skills: string[];
  applicants: number;
  new: number;
  screening: number;
  waiting_interview: number;
  to_review: number;
  needs_attention: number;
  shortlisted: number;
  avg_score: number | null;
  top_score: number | null;
  blocked: number;
  funnel: FunnelStep[];
  last_activity_at: string | null;
}

export interface Overview {
  jobs: OverviewJob[];
  jobs_total: number;
  jobs_active: number;
  applications_total: number;
  interviews_pending: number;
  evaluated: number;
  shortlisted: number;
  needs_attention: number;
  avg_composite: number | null;
  recent: OverviewApp[];
  recent_interviews: OverviewApp[];
  new_count: number;
  attention: OverviewApp[];
  awaiting_decision: OverviewApp[];
}
