import clsx from "clsx";
import { AlertTriangle, CheckCircle2, Globe, Mail, MapPin, Phone, ShieldAlert, ShieldCheck, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer } from "recharts";
import { errorMessage, fetchBlobUrl } from "../api/client";
import type { ApplicationDetail, IntegrityReport, InterviewResponse } from "../api/types";
import { CHART, fmtScore, recommendation } from "../lib/format";
import { AudioPlayer } from "./AudioPlayer";
import { GithubIcon, LinkedinIcon } from "./BrandIcons";
import { HBars, VBars, scoreColor } from "./charts";
import { Avatar, Badge, Button } from "./ui";

/** Score parts as percent of their maximum. */
export function scoreParts(d: ApplicationDetail) {
  const s = d.scores;
  if (!s) return [];
  return [
    { part: "Skills", value: s.skill_score, max: 40 },
    { part: "Experience", value: s.experience_score, max: 20 },
    { part: "Education", value: s.education_score, max: 10 },
    { part: "Interview", value: s.interview_score, max: 30 },
  ].map((p) => ({ ...p, percent: p.value === null ? null : Math.round((p.value / p.max) * 100) }));
}

/** Photo, name, contact and links. */
export function CandidateHeader({ d, compact }: { d: ApplicationDetail; compact?: boolean }) {
  const c = d.candidate;
  const snap = d.profile_snapshot;
  const links = [
    c.linkedin_url && { href: c.linkedin_url, label: "LinkedIn", icon: <LinkedinIcon className="h-3.5 w-3.5" /> },
    c.github_url && { href: c.github_url, label: "GitHub", icon: <GithubIcon className="h-3.5 w-3.5" /> },
    c.portfolio_url && { href: c.portfolio_url, label: "Portfolio", icon: <Globe className="h-3.5 w-3.5" /> },
  ].filter(Boolean) as { href: string; label: string; icon: JSX.Element }[];
  return (
    <div className="flex items-start gap-4">
      <Avatar name={c.full_name} src={c.photo_url} size={compact ? 64 : 80} />
      <div className="min-w-0">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">{c.full_name}</h1>
        {c.headline && <p className="text-sm text-slate-600">{c.headline}</p>}
        <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
          <span className="flex items-center gap-1"><Mail className="h-3.5 w-3.5" />{c.email}</span>
          {c.phone && <span className="flex items-center gap-1"><Phone className="h-3.5 w-3.5" />{c.phone}</span>}
          {c.city && <span className="flex items-center gap-1"><MapPin className="h-3.5 w-3.5" />{c.city}</span>}
          {snap?.highest_degree_label && <span>{snap.highest_degree_label}{snap.field_of_study ? `, ${snap.field_of_study}` : ""}</span>}
        </div>
        {links.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {links.map((l) => (
              <a key={l.label} href={l.href} target="_blank" rel="noopener noreferrer nofollow"
                className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-700 hover:border-slate-300 hover:bg-slate-50">
                {l.icon}{l.label}
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/** Big final score with the plain-language recommendation. */
export function ScoreBadge({ d }: { d: ApplicationDetail }) {
  const s = d.scores;
  const rec = recommendation(s?.composite_score);
  return (
    <div className="flex items-center gap-4 rounded-xl border border-slate-200 px-5 py-3">
      <div>
        <div className="text-xs text-slate-500">Final score</div>
        <div className="text-3xl font-bold tabular-nums" style={{ color: s ? scoreColor(s.composite_score) : CHART.slate }}>
          {fmtScore(s?.composite_score)}<span className="text-sm font-medium text-slate-400">/100</span>
        </div>
      </div>
      <div className="flex flex-col items-start gap-1">
        {rec && <Badge tone={rec.tone}>{rec.label}</Badge>}
        {s?.incomplete && <span className="text-[11px] text-slate-500">Interview not finished</span>}
      </div>
    </div>
  );
}

/** Radar of the four parts next to bars with exact points. */
export function ScoreOverview({ d, height = 220 }: { d: ApplicationDetail; height?: number }) {
  const parts = scoreParts(d);
  if (!parts.length) return <p className="text-sm text-slate-500">No AI scores yet.</p>;
  return (
    <div className="grid items-center gap-6 md:grid-cols-2">
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={parts.map((p) => ({ part: p.part, percent: p.percent ?? 0 }))} outerRadius="75%">
            <PolarGrid stroke={CHART.grid} />
            <PolarAngleAxis dataKey="part" tick={{ fontSize: 12, fill: CHART.axis }} />
            <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
            <Radar dataKey="percent" stroke={CHART.brand} fill={CHART.brand} fillOpacity={0.2} strokeWidth={2} isAnimationActive={false} />
          </RadarChart>
        </ResponsiveContainer>
      </div>
      <ul className="space-y-3">
        {parts.map((p) => (
          <li key={p.part}>
            <div className="mb-1 flex justify-between text-sm">
              <span className="text-slate-600">{p.part}</span>
              <span className="font-semibold tabular-nums text-slate-900">{p.value === null ? "Pending" : `${fmtScore(p.value)} / ${p.max}`}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full" style={{ width: `${p.percent ?? 0}%`, background: p.percent === null ? CHART.slate : scoreColor(p.percent) }} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The job's minimum requirements against what the candidate's profile said when they applied. */
export function RequirementList({ d }: { d: ApplicationDetail }) {
  if (!d.requirements.length) return <p className="text-sm text-slate-500">This job has no minimum degree, experience or CGPA.</p>;
  return (
    <ul className="divide-y divide-slate-100">
      {d.requirements.map((c) => (
        <li key={c.rule} className="flex items-center gap-3 py-2 text-sm">
          {c.ok ? <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" /> : <XCircle className="h-4 w-4 shrink-0 text-rose-600" />}
          <span className="flex-1 text-slate-600">{c.label}<span className="block text-xs text-slate-400">{c.required}</span></span>
          <span className="font-medium text-slate-900">{c.yours}</span>
        </li>
      ))}
    </ul>
  );
}

export function Mismatches({ items }: { items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
      <p className="flex items-center gap-2 font-semibold"><AlertTriangle className="h-4 w-4" /> Check these</p>
      <ul className="mt-1.5 list-disc space-y-0.5 pl-6">{items.map((m) => <li key={m}>{m}</li>)}</ul>
    </div>
  );
}

export function SkillMatch({ d }: { d: ApplicationDetail }) {
  const p = d.parsed_resume;
  if (!p) return <p className="text-sm text-slate-500">The resume has not been read yet.</p>;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">
        {d.required_skills.map((k) => {
          const has = p.matched_skills.some((m) => m.toLowerCase() === k.toLowerCase());
          return (
            <span key={k} className={clsx("inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset",
              has ? "bg-emerald-50 text-emerald-700 ring-emerald-200" : "bg-rose-50 text-rose-700 ring-rose-200")}>
              {has ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}{k}
            </span>
          );
        })}
      </div>
      <p className="text-xs text-slate-500">{p.matched_skills.length} of {d.required_skills.length} required skills found in the resume.</p>
    </div>
  );
}

/** Score for each interview answer as a bar chart. */
export function AnswerChart({ responses }: { responses: InterviewResponse[] }) {
  const data = responses.map((r) => ({ q: `Q${r.question_index + 1}`, score: r.pending ? 0 : r.score }));
  return <VBars data={data} x="q" y="score" yMax={10} name="Score /10" height={180} colorFor={(r) => scoreColor(Number(r.score), 10)} />;
}

function AudioButton({ appId, index }: { appId: string; index: number }) {
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);
  if (url) return <AudioPlayer src={url} autoPlay className="h-10 w-full max-w-sm" />;
  return (
    <Button size="sm" variant="secondary" loading={loading} onClick={async () => {
      setLoading(true);
      try { setUrl(await fetchBlobUrl(`/applications/${appId}/audio/${index}`)); }
      catch (err) { toast.error(errorMessage(err, "Recording not available")); }
      finally { setLoading(false); }
    }}>
      Play answer
    </Button>
  );
}

export function Answer({ appId, r, printable }: { appId: string; r: InterviewResponse; printable?: boolean }) {
  return (
    <div className="break-inside-avoid rounded-lg border border-slate-200 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs font-medium text-slate-500">
            Question {r.question_index + 1} · {r.focus}
            {r.kind === "follow_up" && <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 font-medium text-amber-800">Follow-up</span>}
          </div>
          <p className="mt-1 font-medium text-slate-900">{r.question}</p>
        </div>
        {r.pending ? <Badge tone="amber">Scoring soon</Badge> : (
          <span className="shrink-0 rounded-md px-2 py-1 text-sm font-semibold tabular-nums" style={{ color: scoreColor(r.score, 10), background: "#f8fafc" }}>{fmtScore(r.score)}/10</span>
        )}
      </div>
      <p className="mt-3 border-l-2 border-slate-200 pl-3 text-sm text-slate-700">
        {r.transcript ? r.transcript : <span className="text-slate-400">No speech detected.</span>}
      </p>
      {!r.pending && (
        <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-500">
          <span>Accuracy <b className="text-slate-800">{fmtScore(r.accuracy)}</b></span>
          <span>Relevance <b className="text-slate-800">{fmtScore(r.relevance)}</b></span>
          <span>Clarity <b className="text-slate-800">{fmtScore(r.clarity)}</b></span>
        </div>
      )}
      {r.feedback && <p className="mt-2 text-sm text-slate-600">{r.feedback}</p>}
      {r.has_audio && !printable && <div className="mt-3 no-print"><AudioButton appId={appId} index={r.question_index} /></div>}
    </div>
  );
}

const LEVEL = {
  clean: { cls: "border-emerald-200 bg-emerald-50 text-emerald-900", title: "No integrity issues", Icon: ShieldCheck },
  warning: { cls: "border-amber-300 bg-amber-50 text-amber-900", title: "Check the interview log", Icon: ShieldAlert },
  high: { cls: "border-rose-300 bg-rose-50 text-rose-900", title: "Possible cheating: review carefully", Icon: ShieldAlert },
} as const;

export function IntegritySummary({ report }: { report: IntegrityReport }) {
  const st = LEVEL[report.level];
  return (
    <div className={clsx("rounded-lg border p-4", st.cls)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-2 font-semibold"><st.Icon className="h-5 w-5" />{st.title}</p>
        <span className="text-sm">Warnings <b>{report.strikes}/{report.max_strikes}</b></span>
      </div>
      {report.terminated && <p className="mt-2 text-sm"><b>The interview was ended automatically.</b> {report.terminated_reason} Unanswered questions scored 0.</p>}
      {report.counts.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {report.counts.map((c) => <span key={c.type} className="rounded-full bg-white/70 px-2.5 py-1 text-xs font-medium ring-1 ring-black/5">{c.label} × {c.count}</span>)}
        </div>
      )}
    </div>
  );
}

/** Two small charts: events per question, and how much of each answer was spent looking at the screen. */
export function IntegrityCharts({ report, questions }: { report: IntegrityReport; questions: number }) {
  const per = Array.from({ length: Math.max(questions, 1) }, (_, i) => ({ q: `Q${i + 1}`, events: 0 }));
  for (const e of report.events) {
    if (e.question_index !== null && e.type !== "question_repeated" && per[e.question_index]) per[e.question_index].events++;
  }
  return (
    <div className="grid gap-5 md:grid-cols-2">
      <div>
        <p className="mb-2 text-sm font-medium text-slate-700">Flags per question</p>
        <VBars data={per} x="q" y="events" name="Flags" height={160} color="#404040" />
      </div>
      <div>
        <p className="mb-2 text-sm font-medium text-slate-700">Looking at the screen{report.attention ? ` (average ${Math.round(report.attention.average)}%)` : ""}</p>
        {report.attention ? (
          <HBars max={100} suffix="%" data={report.attention.per_question.map((q) => ({ label: `Question ${q.question_index + 1}`, value: Math.round(q.percent), color: scoreColor(q.percent) }))} />
        ) : <p className="py-6 text-sm text-slate-400">No webcam data was recorded.</p>}
      </div>
    </div>
  );
}

function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function EventTimeline({ report }: { report: IntegrityReport }) {
  const notable = report.events.filter((e) => e.type !== "question_repeated");
  if (!notable.length) return <p className="text-sm text-slate-500">Nothing was flagged during the interview.</p>;
  return (
    <ol className="relative space-y-2 border-l border-slate-200 pl-4 text-sm">
      {notable.map((e, i) => (
        <li key={i} className="relative">
          <span className={clsx("absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full ring-2 ring-white", e.strike ? "bg-rose-500" : "bg-slate-300")} />
          <span className="mr-2 text-xs tabular-nums text-slate-400">{fmtTime(e.at)}</span>
          {e.question_index !== null && <span className="mr-1 text-xs font-medium text-slate-500">Q{e.question_index + 1}</span>}
          <span className="text-slate-800">{e.label}</span>
          {e.detail && <span className="text-slate-500"> ({e.detail})</span>}
          {e.strike && <span className="ml-1 text-xs font-semibold text-rose-600">warning</span>}
        </li>
      ))}
    </ol>
  );
}

function Snapshot({ appId, snap }: { appId: string; snap: IntegrityReport["snapshots"][number] }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let u: string | null = null;
    fetchBlobUrl(`/applications/${appId}/snapshots/${snap.index}`)
      .then((x) => { u = x; setUrl(x); })
      .catch(() => setFailed(true));
    return () => { if (u) URL.revokeObjectURL(u); };
  }, [appId, snap.index]);
  const flagged = snap.reason !== "start" && snap.reason !== "random";
  return (
    <figure className={clsx("break-inside-avoid overflow-hidden rounded-lg bg-white ring-1", flagged ? "ring-2 ring-rose-400" : "ring-black/10")}>
      {url ? (
        <a href={url} target="_blank" rel="noreferrer"><img src={url} alt={`Webcam photo: ${snap.label}`} className="aspect-[4/3] w-full -scale-x-100 object-cover" /></a>
      ) : (
        <div className="flex aspect-[4/3] items-center justify-center bg-slate-100 text-[10px] text-slate-400">{failed ? "Not available" : "Loading…"}</div>
      )}
      <figcaption className={clsx("px-1.5 py-1 text-[10px] leading-tight", flagged ? "font-semibold text-rose-700" : "text-slate-600")}>
        {snap.question_index !== null ? `Q${snap.question_index + 1} · ` : ""}{snap.label}<span className="block font-normal opacity-70">{fmtTime(snap.at)}</span>
      </figcaption>
    </figure>
  );
}

export function Snapshots({ appId, report }: { appId: string; report: IntegrityReport }) {
  if (!report.snapshots.length) return <p className="text-sm text-slate-500">No webcam photos were taken.</p>;
  return (
    <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-6">
      {report.snapshots.map((s) => <Snapshot key={s.index} appId={appId} snap={s} />)}
    </div>
  );
}
