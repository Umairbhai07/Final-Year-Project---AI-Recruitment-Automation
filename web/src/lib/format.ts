import type { Decision, EducationLevel, Stage } from "../api/types";

export const STAGE_LABEL: Record<Stage, string> = {
  submitted: "Submitted",
  under_review: "Under review",
  screening_failed: "Needs manual review",
  not_qualified: "Not qualified",
  interview_invited: "Interview invited",
  interview_in_progress: "Interviewing",
  evaluated: "Evaluated",
};

export const STAGE_TONE: Record<Stage, Tone> = {
  submitted: "gray",
  under_review: "blue",
  screening_failed: "amber",
  not_qualified: "gray",
  interview_invited: "violet",
  interview_in_progress: "blue",
  evaluated: "green",
};

export const DECISION_TONE: Record<Decision, Tone> = { pending: "gray", shortlisted: "green", rejected: "red" };

export const EDUCATION_LABEL: Record<EducationLevel, string> = {
  none: "No requirement",
  matric: "Matric / O-Levels",
  high_school: "Intermediate / A-Levels",
  diploma: "Diploma",
  bachelors: "Bachelor's",
  masters: "Master's",
  phd: "PhD",
};

export type Tone = "gray" | "blue" | "green" | "red" | "amber" | "violet" | "brand";

export const fmtDate = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "—";

export const fmtScore = (v: number | null | undefined) => (v === null || v === undefined ? "—" : Number(v).toFixed(1).replace(/\.0$/, ""));

export const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export function scoreColor(pct: number) {
  // black and white: a stronger score is a darker bar
  if (pct >= 70) return "bg-neutral-950";
  if (pct >= 45) return "bg-neutral-500";
  return "bg-neutral-300";
}

/** "just now", "5 min ago", "3 h ago", "yesterday", "4 days ago", then the date. */
export function fmtAgo(iso: string | null | undefined, now = Date.now()) {
  if (!iso) return "";
  const secs = Math.max(0, (now - new Date(iso).getTime()) / 1000);
  if (secs < 60) return "just now";
  if (secs < 3600) return `${Math.floor(secs / 60)} min ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)} h ago`;
  const days = Math.floor(secs / 86400);
  if (days === 1) return "yesterday";
  if (days < 7) return `${days} days ago`;
  return fmtDate(iso);
}

const AVATAR_GRADIENTS = [
  "from-neutral-900 to-neutral-700", "from-neutral-800 to-neutral-600", "from-neutral-700 to-neutral-500",
  "from-neutral-950 to-neutral-800", "from-neutral-600 to-neutral-400", "from-neutral-800 to-neutral-500",
];

/** A stable colour for a person's avatar, picked from their name. */
export function avatarGradient(name: string): string {
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return AVATAR_GRADIENTS[h % AVATAR_GRADIENTS.length];
}

/** Degree names a candidate picks from (same order as the server's ranking). */
export const DEGREE_OPTIONS: { value: EducationLevel; label: string }[] = [
  { value: "none", label: "No formal degree" },
  { value: "matric", label: "Matric / O-Levels" },
  { value: "high_school", label: "Intermediate / A-Levels" },
  { value: "diploma", label: "Diploma (e.g. DAE)" },
  { value: "bachelors", label: "Bachelor's" },
  { value: "masters", label: "Master's" },
  { value: "phd", label: "PhD" },
];

/** A plain-language reading of the final score (a guide for the recruiter, not a decision). */
export function recommendation(score: number | null | undefined): { label: string; tone: Tone } | null {
  if (score === null || score === undefined) return null;
  if (score >= 75) return { label: "Strong match", tone: "green" };
  if (score >= 60) return { label: "Good match", tone: "blue" };
  if (score >= 45) return { label: "Borderline", tone: "amber" };
  return { label: "Weak match", tone: "red" };
}

export const fmtYears = (v: number | null | undefined) =>
  v === null || v === undefined ? "—" : `${Number(v.toFixed(1))} yr${v === 1 ? "" : "s"}`;

/** Chart colours used everywhere, so the same thing has the same colour on every page. */
export const CHART = {
  brand: "#0a0a0a",
  brandSoft: "#d4d4d4",
  teal: "#525252",
  amber: "#d97706",
  rose: "#e11d48",
  slate: "#a3a3a3",
  grid: "#e5e5e5",
  axis: "#737373",
};
