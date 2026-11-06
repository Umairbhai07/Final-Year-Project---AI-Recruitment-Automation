import { useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { AlertTriangle, ChevronDown, Download, Flag, Search, ShieldAlert, SlidersHorizontal } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { Link, useNavigate, useParams } from "react-router-dom";
import { downloadFile, errorMessage } from "../../api/client";
import { jobsApi } from "../../api/endpoints";
import type { CandidateFilters, CandidateRow, Decision, JobStats, Stage } from "../../api/types";
import { Disclaimer } from "../../components/Disclaimer";
import { Donut, Funnel, HBars, VBars, scoreColor } from "../../components/charts";
import { Menu } from "../../components/Menu";
import { Avatar, Badge, Button, Card, EmptyState, ErrorState, FullPageSpinner, Panel, ScoreChip, Skeleton, Tabs } from "../../components/ui";
import { prefetchProps } from "../../lib/prefetch";
import { CHART, DECISION_TONE, EDUCATION_LABEL, STAGE_LABEL, STAGE_TONE, capitalize, fmtAgo, fmtScore } from "../../lib/format";

const needsReview = (r: CandidateRow) =>
  r.needs_manual_review || r.issue_reported || r.integrity_level === "high" || r.integrity_level === "warning" || r.mismatch_count > 0;

/** Quick views over the list. Counts are worked out from the loaded candidates. */
const VIEWS: { key: string; label: string; test: (r: CandidateRow) => boolean }[] = [
  { key: "all", label: "All", test: () => true },
  { key: "new", label: "New", test: (r) => r.is_new },
  { key: "done", label: "Interview done", test: (r) => r.interview_completed_at !== null },
  { key: "waiting", label: "Waiting for interview", test: (r) => r.stage === "interview_invited" || r.stage === "interview_in_progress" },
  { key: "review", label: "Needs review", test: needsReview },
  { key: "shortlisted", label: "Shortlisted", test: (r) => r.decision === "shortlisted" },
  { key: "not_qualified", label: "Not qualified", test: (r) => r.stage === "not_qualified" },
];

const DEFAULT_FILTERS: CandidateFilters = { sort: "recent", stage: "", decision: "" };

export default function JobDashboard() {
  const { id } = useParams();
  const [tab, setTab] = useState<"candidates" | "insights">("candidates");
  const [exporting, setExporting] = useState(false);

  const job = useQuery({ queryKey: ["job", id], queryFn: () => jobsApi.get(id!) });
  const stats = useQuery({ queryKey: ["stats", id], queryFn: () => jobsApi.stats(id!), refetchInterval: 15_000 });

  const exportAs = async (format: "csv" | "pdf", onlyShortlisted: boolean) => {
    setExporting(true);
    try {
      await downloadFile(`/jobs/${id}/export`, { format, only_shortlisted: onlyShortlisted }, `candidates.${format}`);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setExporting(false);
    }
  };

  if (job.isLoading) return <FullPageSpinner />;
  if (job.error || !job.data) return <ErrorState message={errorMessage(job.error)} />;
  const j = job.data;
  const s = stats.data;
  const reqs = [
    j.education_level !== "none" && `${EDUCATION_LABEL[j.education_level]}+`,
    j.min_experience_years > 0 && `${j.min_experience_years}+ yrs`,
    j.min_cgpa && `CGPA ${j.min_cgpa.toFixed(2)}+`,
  ].filter(Boolean).join(" · ");

  return (
    <>
      <Link to="/recruiter" className="mb-3 inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-900">← Jobs</Link>
      <div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-[26px]">{j.title}</h1>
            <Badge tone={j.status === "active" ? "green" : j.status === "paused" ? "amber" : "gray"} className="capitalize">{j.status}</Badge>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            {reqs ? <>Minimum: {reqs}</> : "No minimum requirements"} · Resume threshold {j.screening_threshold}/70 · {j.num_questions} interview questions
          </p>
        </div>
        <div className="flex gap-2">
          {j.status !== "closed" && <Link to={`/recruiter/jobs/${id}/edit`}><Button variant="secondary" size="sm">Edit job</Button></Link>}
          <Menu label="Export"
            trigger={() => <Button variant="secondary" size="sm" loading={exporting}><Download className="h-3.5 w-3.5" /> Export <ChevronDown className="h-3.5 w-3.5" /></Button>}
            items={[
              { label: "All candidates (PDF)", onClick: () => exportAs("pdf", false) },
              { label: "All candidates (CSV)", onClick: () => exportAs("csv", false) },
              { label: "Shortlist only (PDF)", onClick: () => exportAs("pdf", true) },
            ]} />
        </div>
      </div>
      <Disclaimer />

      <Kpis s={s} />

      <Tabs className="mt-6" value={tab} onChange={setTab} tabs={[
        { value: "candidates", label: "Candidates", count: s?.total },
        { value: "insights", label: "Charts" },
      ]} />
      <div className="mt-5">
        {tab === "candidates" ? <Candidates jobId={id!} total={s?.total ?? 0} /> : <Insights s={s} />}
      </div>
    </>
  );
}

function Kpis({ s }: { s?: JobStats }) {
  const items = [
    { label: "Applicants", value: s?.total },
    { label: "Passed screening", value: s?.funnel.find((f) => f.key === "qualified")?.count },
    { label: "Interviewed", value: s?.interviewed },
    { label: "Shortlisted", value: s?.by_decision.shortlisted },
    { label: "Average score", value: s ? fmtScore(s.avg_composite) : undefined },
    { label: "Stopped by requirements", value: s?.blocked_applications, muted: true },
  ];
  return (
    <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-slate-200 bg-slate-200 sm:grid-cols-3 lg:grid-cols-6">
      {items.map((k) => (
        <div key={k.label} className="bg-white px-4 py-3">
          <div className="truncate text-xs text-slate-500">{k.label}</div>
          <div className={clsx("text-xl font-bold tabular-nums", k.muted ? "text-slate-500" : "text-slate-900")}>{k.value ?? "—"}</div>
        </div>
      ))}
    </div>
  );
}

function Insights({ s }: { s?: JobStats }) {
  if (!s) return <div className="grid gap-5 lg:grid-cols-2">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-64 rounded-xl" />)}</div>;
  const funnel = s.funnel.filter((f) => f.key !== "blocked");
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Panel title="Hiring funnel" subtitle={s.blocked_applications ? `${s.blocked_applications} did not meet the minimum requirements in their resume` : "How many candidates reach each step"}>
        <Funnel steps={funnel} />
      </Panel>
      <Panel title="Final score spread" subtitle="Candidates by final score out of 100">
        <VBars data={s.histogram} x="range" y="count" name="Candidates" height={190}
          colorFor={(r) => scoreColor(Number(String(r.range).split("-")[0]) + 5)} />
      </Panel>
      <Panel title="Average score by part" subtitle="Percent of the maximum for each part, across evaluated candidates">
        <HBars data={s.breakdown.filter((b) => b.percent !== null).map((b) => ({ label: b.part, value: Math.round(b.percent!), color: scoreColor(b.percent!) }))}
          max={100} suffix="%" />
      </Panel>
      <Panel title="Skills most often missing" subtitle="Required skills the resumes did not show">
        <HBars data={s.missing_skills.map((m) => ({ label: m.skill, value: m.count }))} color={CHART.brand} empty="Every candidate shows all the skills" />
      </Panel>
      <Panel title="Interview integrity">
        <Donut data={[
          { label: "Clean", value: s.integrity.clean, color: CHART.brandSoft },
          { label: "Warnings", value: s.integrity.warning, color: "#737373" },
          { label: "Possible cheating", value: s.integrity.high, color: CHART.brand },
        ]} />
      </Panel>
      <Panel title="Education of applicants" subtitle={s.mismatches ? `${s.mismatches} application${s.mismatches === 1 ? "" : "s"} to check (answers differ from the resume, or a duplicate account)` : "From the resumes"}>
        <Donut data={s.degrees.map((d, i) => ({ label: d.label, value: d.count, color: [CHART.brand, "#737373", CHART.slate, CHART.brandSoft, "#e5e5e5"][i % 5] }))} />
      </Panel>
    </div>
  );
}

function Candidates({ jobId, total }: { jobId: string; total: number }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [filters, setFilters] = useState<CandidateFilters>(DEFAULT_FILTERS);
  const [view, setView] = useState("all");
  const [search, setSearch] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const rows = useQuery({
    queryKey: ["candidates", jobId, filters],
    queryFn: () => jobsApi.candidates(jobId, filters),
    refetchInterval: 15_000,
    placeholderData: (prev) => prev,
  });

  // Tell the recruiter when someone finishes an interview while this page is open.
  const finished = useRef<Set<string> | null>(null);
  useEffect(() => {
    if (!rows.data) return;
    const done = rows.data.filter((r) => r.interview_completed_at);
    if (finished.current) {
      for (const r of done) {
        if (!finished.current.has(r.application_id)) toast.success(`${r.full_name} just finished the interview`, { icon: "🎤" });
      }
    }
    finished.current = new Set([...(finished.current ?? []), ...done.map((r) => r.application_id)]);
  }, [rows.data]);

  const all = rows.data ?? [];
  const active = VIEWS.find((v) => v.key === view) ?? VIEWS[0];
  const q = search.trim().toLowerCase();
  const shown = all.filter((r) => active.test(r) && (!q || r.full_name.toLowerCase().includes(q) || r.email.toLowerCase().includes(q)));
  const filtered = filters.stage || filters.decision || filters.min_score !== undefined || filters.max_score !== undefined;

  return (
    <Card>
      <div className="flex flex-col gap-3 border-b border-slate-100 p-4 lg:flex-row lg:items-center">
        <div className="flex flex-1 flex-wrap gap-1.5">
          {VIEWS.map((v) => {
            const n = all.filter(v.test).length;
            if (v.key !== "all" && !n) return null;
            return (
              <button key={v.key} type="button" onClick={() => setView(v.key)}
                className={clsx("h-8 rounded-full px-3 text-sm transition",
                  view === v.key ? "bg-slate-900 font-medium text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200")}>
                {v.label} <span className={clsx("tabular-nums", view === v.key ? "text-slate-300" : "text-slate-400")}>{n}</span>
              </button>
            );
          })}
        </div>
        <div className="flex w-full flex-wrap gap-2 sm:w-auto">
          <div className="relative min-w-0 flex-1 basis-full sm:basis-auto">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input className="input h-9 w-full pl-9 text-sm sm:w-48" placeholder="Find a candidate" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Find a candidate" />
          </div>
          <select className="select h-9 min-w-0 flex-1 text-sm sm:w-44 sm:flex-none" aria-label="Sort by" value={filters.sort} onChange={(e) => setFilters((f) => ({ ...f, sort: e.target.value as CandidateFilters["sort"] }))}>
            <option value="recent">Latest activity</option>
            <option value="composite">Final score</option>
            <option value="resume">Resume score</option>
            <option value="interview">Interview score</option>
            <option value="date">Newest applicants</option>
            <option value="name">Name</option>
          </select>
          <Button variant={filtered ? "primary" : "secondary"} size="sm" className="h-9" onClick={() => setShowFilters((v) => !v)} aria-expanded={showFilters}>
            <SlidersHorizontal className="h-3.5 w-3.5" /> Filters
          </Button>
        </div>
      </div>

      {showFilters && (
        <div className="grid grid-cols-2 gap-3 border-b border-slate-100 bg-slate-50/60 p-4 md:grid-cols-5 md:items-end">
          <div>
            <label className="label text-xs" htmlFor="min">Min score</label>
            <input id="min" type="number" min={0} max={100} className="input h-9" placeholder="0"
              value={filters.min_score ?? ""} onChange={(e) => setFilters((f) => ({ ...f, min_score: e.target.value === "" ? undefined : Number(e.target.value) }))} />
          </div>
          <div>
            <label className="label text-xs" htmlFor="max">Max score</label>
            <input id="max" type="number" min={0} max={100} className="input h-9" placeholder="100"
              value={filters.max_score ?? ""} onChange={(e) => setFilters((f) => ({ ...f, max_score: e.target.value === "" ? undefined : Number(e.target.value) }))} />
          </div>
          <div>
            <label className="label text-xs" htmlFor="stage">Stage</label>
            <select id="stage" className="select h-9" value={filters.stage} onChange={(e) => setFilters((f) => ({ ...f, stage: e.target.value as Stage | "" }))}>
              <option value="">All stages</option>
              {Object.entries(STAGE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
          <div>
            <label className="label text-xs" htmlFor="decision">Decision</label>
            <select id="decision" className="select h-9" value={filters.decision} onChange={(e) => setFilters((f) => ({ ...f, decision: e.target.value as Decision | "" }))}>
              <option value="">All decisions</option>
              <option value="pending">Pending</option>
              <option value="shortlisted">Shortlisted</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>
          <Button variant="ghost" size="sm" onClick={() => { setFilters(DEFAULT_FILTERS); setView("all"); setSearch(""); }}>Clear all</Button>
        </div>
      )}

      {rows.isLoading ? (
        <div className="space-y-2 p-5">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-14" />)}</div>
      ) : rows.error ? (
        <div className="p-4"><ErrorState message={errorMessage(rows.error)} onRetry={() => rows.refetch()} /></div>
      ) : !shown.length ? (
        <div className="p-4">
          <EmptyState title={total ? (view === "new" ? "Nothing new since you last looked" : "No candidates match") : "No applicants yet"}
            text={total ? "Try another view or clear the filters." : "Applications will appear here and are screened automatically."} />
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-left text-xs font-medium text-slate-500">
              <tr className="border-b border-slate-100">
                <th className="w-12 px-4 py-2.5">#</th>
                <th className="px-4 py-2.5">Candidate</th>
                <th className="px-4 py-2.5">Final score</th>
                <th className="px-3 py-2.5">Resume</th>
                <th className="px-3 py-2.5">Interview</th>
                <th className="px-4 py-2.5">Stage</th>
                <th className="px-4 py-2.5"><span className="sr-only">Flags</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {shown.map((r) => (
                <tr key={r.application_id} {...prefetchProps(qc, `/recruiter/applications/${r.application_id}`)}
                  className={clsx("cursor-pointer transition-colors hover:bg-slate-50", r.is_new && "bg-brand-50/40")}
                  onClick={() => navigate(`/recruiter/applications/${r.application_id}`)}>
                  <td className="px-4 py-3 text-xs font-semibold tabular-nums text-slate-400">{r.composite_score !== null ? r.rank : "–"}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <Avatar name={r.full_name} src={r.photo_url} size={36} />
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <Link to={`/recruiter/applications/${r.application_id}`} className="font-medium text-slate-900 hover:text-brand-700" onClick={(e) => e.stopPropagation()}>{r.full_name}</Link>
                          {r.is_new && <span className="h-2 w-2 rounded-full bg-brand-600" title="New activity" />}
                        </div>
                        <div className="truncate text-xs text-slate-500">
                          {[r.degree, r.experience_years !== null && `${r.experience_years} yrs`, r.cgpa !== null && `CGPA ${r.cgpa.toFixed(2)}`, r.city].filter(Boolean).join(" · ")}
                        </div>
                        {r.last_activity && <div className="text-xs text-slate-400">{r.last_activity} · {fmtAgo(r.last_activity_at)}</div>}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <ScoreChip value={r.composite_score} />
                    {r.incomplete && r.composite_score !== null && (r.stage === "interview_invited" || r.stage === "interview_in_progress") && <div className="mt-0.5 text-[11px] text-slate-400">resume only</div>}
                  </td>
                  <td className="px-3 py-3 tabular-nums text-slate-700">{fmtScore(r.resume_total)}<span className="text-slate-400">/70</span></td>
                  <td className="px-3 py-3 tabular-nums text-slate-700">{fmtScore(r.interview_score)}<span className="text-slate-400">/30</span></td>
                  <td className="px-4 py-3">
                    <div className="flex flex-col items-start gap-1">
                      <Badge tone={STAGE_TONE[r.stage]}>{STAGE_LABEL[r.stage]}</Badge>
                      {r.decision !== "pending" && <Badge tone={DECISION_TONE[r.decision]}>{capitalize(r.decision)}</Badge>}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1.5">
                      {r.mismatch_count > 0 && <span title="Answers and resume differ, or a duplicate account"><AlertTriangle className="h-4 w-4 text-amber-500" aria-label="Answers and resume differ, or a duplicate account" /></span>}
                      {r.needs_manual_review && <span title="Needs manual review"><AlertTriangle className="h-4 w-4 text-slate-400" aria-label="Needs manual review" /></span>}
                      {r.issue_reported && <span title="Candidate reported a technical issue"><Flag className="h-4 w-4 text-rose-500" aria-label="Issue reported" /></span>}
                      {(r.integrity_level === "high" || r.integrity_level === "warning") && (
                        <span title={r.integrity_level === "high" ? "Possible cheating in the interview" : "Interview integrity warning"}>
                          <ShieldAlert className={r.integrity_level === "high" ? "h-4 w-4 text-rose-600" : "h-4 w-4 text-amber-500"} aria-label={r.integrity_level === "high" ? "Possible cheating" : "Integrity warning"} />
                        </span>
                      )}
                      {r.archived && <Badge tone="gray">Archived</Badge>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
