import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Briefcase, MoreHorizontal, Plus, Search } from "lucide-react";
import { useState } from "react";
import toast from "react-hot-toast";
import { Link, useNavigate } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { dashboardApi, jobsApi } from "../../api/endpoints";
import type { JobStatus, OverviewJob } from "../../api/types";
import { Disclaimer } from "../../components/Disclaimer";
import { Menu } from "../../components/Menu";
import { Badge, Button, ConfirmDialog, EmptyState, ErrorState, ListSkeleton, PageHeader, ScoreChip } from "../../components/ui";
import { prefetchProps } from "../../lib/prefetch";
import { CHART, fmtAgo, fmtDate } from "../../lib/format";

const STATUS_TONE = { active: "green", paused: "amber", closed: "gray" } as const;
const FILTERS: { value: "all" | JobStatus; label: string }[] = [
  { value: "all", label: "All" },
  { value: "active", label: "Active" },
  { value: "paused", label: "Paused" },
  { value: "closed", label: "Closed" },
];

/** The recruiter's home: one row per job, so each job's candidates are reviewed on their own page. */
export default function Overview() {
  const qc = useQueryClient();
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["overview"], queryFn: dashboardApi.overview, refetchInterval: 20_000 });
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all" | JobStatus>("all");
  const [closing, setClosing] = useState<OverviewJob | null>(null);

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: JobStatus }) => jobsApi.setStatus(id, status),
    onSuccess: (job) => {
      toast.success(`Job ${job.status === "active" ? "resumed" : job.status}`);
      qc.invalidateQueries({ queryKey: ["overview"] });
      qc.invalidateQueries({ queryKey: ["jobs"] });
      setClosing(null);
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const header = (
    <PageHeader title="Jobs" subtitle="Open a job to see its candidates, charts and reports."
      actions={<Link to="/recruiter/jobs/new"><Button><Plus className="h-4 w-4" /> Post a job</Button></Link>} />
  );
  if (isLoading) return <>{header}<ListSkeleton rows={3} /></>;
  if (error || !data) return <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />;

  const q = search.trim().toLowerCase();
  const shown = data.jobs.filter((j) =>
    (filter === "all" || j.status === filter) &&
    (!q || j.title.toLowerCase().includes(q) || j.required_skills.some((s) => s.toLowerCase().includes(q))));
  const toReview = data.jobs.reduce((n, j) => n + j.to_review, 0);

  return (
    <>
      {header}
      <Disclaimer />

      {data.jobs_total === 0 ? (
        <EmptyState icon={<Briefcase />} title="Post your first job"
          text="Set the minimum degree, experience and CGPA. Candidates who meet them are screened by AI and the best are invited to a voice interview."
          action={<Link to="/recruiter/jobs/new"><Button>Post a job</Button></Link>} />
      ) : (
        <>
          <div className="mb-5 grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-slate-200 bg-slate-200 sm:grid-cols-4">
            <Summary label="Active jobs" value={data.jobs_active} />
            <Summary label="Applicants" value={data.applications_total} />
            <Summary label="Ready to review" value={toReview} accent={toReview > 0} />
            <Summary label="Need attention" value={data.needs_attention} warn={data.needs_attention > 0} />
          </div>

          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input className="input pl-10" placeholder="Search jobs by title or skill" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search jobs" />
            </div>
            <div className="inline-flex rounded-lg bg-slate-100 p-1 text-sm" role="tablist" aria-label="Filter jobs by status">
              {FILTERS.map((f) => {
                const n = f.value === "all" ? data.jobs.length : data.jobs.filter((j) => j.status === f.value).length;
                return (
                  <button key={f.value} role="tab" aria-selected={filter === f.value} onClick={() => setFilter(f.value)}
                    className={clsx("h-8 rounded-md px-3 font-medium transition", filter === f.value ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800")}>
                    {f.label} <span className="text-slate-400">{n}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {!shown.length ? (
            <p className="card px-6 py-10 text-center text-sm text-slate-500">No jobs match.</p>
          ) : (
            <div className="space-y-3">
              {shown.map((job) => (
                <JobCard key={job.id} job={job} prefetch={prefetchProps(qc, `/recruiter/jobs/${job.id}`)}
                  onStatus={(status) => (status === "closed" ? setClosing(job) : setStatus.mutate({ id: job.id, status }))} />
              ))}
            </div>
          )}
        </>
      )}

      <ConfirmDialog
        open={!!closing}
        title="Close this job?"
        message={<>Closing <b>{closing?.title}</b> is permanent. It stops new applications and cancels pending interviews. You can still see its candidates and reports.</>}
        confirmLabel="Close job"
        danger
        loading={setStatus.isPending}
        onConfirm={() => closing && setStatus.mutate({ id: closing.id, status: "closed" })}
        onCancel={() => setClosing(null)}
      />
    </>
  );
}

function Summary({ label, value, accent, warn }: { label: string; value: number; accent?: boolean; warn?: boolean }) {
  return (
    <div className="bg-white px-4 py-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className={clsx("text-xl font-bold tabular-nums", accent ? "text-brand-700" : warn ? "text-amber-600" : "text-slate-900")}>{value}</div>
    </div>
  );
}

function JobCard({ job, prefetch, onStatus }: { job: OverviewJob; prefetch: object; onStatus: (s: JobStatus) => void }) {
  const navigate = useNavigate();
  const url = `/recruiter/jobs/${job.id}`;
  return (
    <div className="card card-hover relative p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Link to={url} {...prefetch} className="text-[16px] font-semibold text-slate-900 after:absolute after:inset-0 hover:text-brand-700">{job.title}</Link>
            <Badge tone={STATUS_TONE[job.status]} className="capitalize">{job.status}</Badge>
            {job.new > 0 && <Badge tone="brand">{job.new} new</Badge>}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Posted {fmtDate(job.created_at)}{job.deadline && <> · Closes {fmtDate(job.deadline)}</>}
            {job.last_activity_at && <> · Last activity {fmtAgo(job.last_activity_at)}</>}
          </p>
          <MiniFunnel job={job} />
        </div>

        <div className="grid grid-cols-4 gap-2 text-center lg:w-[400px]">
          <Count label="Applicants" value={job.applicants} />
          <Count label="To review" value={job.to_review} tone={job.to_review ? "brand" : undefined} />
          <Count label="Attention" value={job.needs_attention} tone={job.needs_attention ? "amber" : undefined} />
          <div>
            <div className="flex h-7 items-center justify-center"><ScoreChip value={job.top_score} /></div>
            <div className="text-[11px] text-slate-500">Top score</div>
          </div>
        </div>

        <JobMenu job={job} onEdit={() => navigate(`${url}/edit`)} onStatus={onStatus} />
      </div>
    </div>
  );
}

function Count({ label, value, tone }: { label: string; value: number; tone?: "brand" | "amber" }) {
  return (
    <div>
      <div className={clsx("text-xl font-bold leading-7 tabular-nums", tone === "brand" ? "text-brand-700" : tone === "amber" ? "text-amber-600" : "text-slate-900")}>{value}</div>
      <div className="text-[11px] text-slate-500">{label}</div>
    </div>
  );
}

/** A thin stacked bar: how far this job's applicants have got. */
function MiniFunnel({ job }: { job: OverviewJob }) {
  const steps = job.funnel.filter((s) => s.key !== "blocked");
  const total = steps[0]?.count ?? 0;
  if (!total && !job.blocked) return <p className="mt-3 text-xs text-slate-400">No applicants yet</p>;
  const colors = [CHART.brandSoft, "#a3a3a3", CHART.brand, CHART.teal];
  return (
    <div className="mt-3 max-w-md">
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-slate-500">
        {steps.map((s, i) => (
          <span key={s.key} className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm" style={{ background: colors[i] }} />{s.label} <b className="font-semibold text-slate-700">{s.count}</b></span>
        ))}
        {job.blocked > 0 && <span className="text-slate-400">· {job.blocked} stopped by requirements</span>}
      </div>
      <div className="mt-1.5 flex h-1.5 overflow-hidden rounded-full bg-slate-100">
        {steps.map((s, i) => {
          const next = steps[i + 1]?.count ?? 0;
          const w = total ? ((s.count - next) / total) * 100 : 0;
          return w > 0 ? <div key={s.key} style={{ width: `${w}%`, background: colors[i] }} /> : null;
        })}
      </div>
    </div>
  );
}

function JobMenu({ job, onEdit, onStatus }: { job: OverviewJob; onEdit: () => void; onStatus: (s: JobStatus) => void }) {
  if (job.status === "closed") return <div className="hidden w-9 lg:block" />;
  return (
    <Menu label="Job actions" className="z-10 self-start lg:self-center"
      trigger={() => (
        <button type="button" aria-label="Job actions" className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-900">
          <MoreHorizontal className="h-5 w-5" />
        </button>
      )}
      items={[
        { label: "Edit", onClick: onEdit },
        { label: "Pause", onClick: () => onStatus("paused"), hidden: job.status !== "active" },
        { label: "Resume", onClick: () => onStatus("active"), hidden: job.status !== "paused" },
        { label: "Close job", onClick: () => onStatus("closed"), danger: true },
      ]} />
  );
}
