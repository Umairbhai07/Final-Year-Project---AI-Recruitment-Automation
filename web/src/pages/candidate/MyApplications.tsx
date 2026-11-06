import { useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Check } from "lucide-react";
import { Link } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { applicationsApi } from "../../api/endpoints";
import type { MyApplication } from "../../api/types";
import { Badge, Button, Card, EmptyState, ErrorState, ListSkeleton, PageHeader } from "../../components/ui";
import { prefetchProps } from "../../lib/prefetch";
import { fmtDate } from "../../lib/format";

const STEPS = ["Submitted", "Under review", "Interview invited", "Interview completed", "Evaluated"];

/** Which tracker step is reached. "Not selected" stops at step 2. */
function Tracker({ app }: { app: MyApplication }) {
  const reviewedOnly = app.status_label === "Not selected";
  const reached = app.stage_step;
  return (
    <ol className="mt-4 grid grid-cols-5 gap-1" aria-label="Application progress">
      {STEPS.map((label, i) => {
        const n = i + 1;
        const done = n < reached || (n === reached && (n === 5 || reviewedOnly));
        const current = n === reached && !done;
        const name = n === 2 && reviewedOnly ? "Not selected" : label;
        return (
          <li key={label} className="flex flex-col items-center text-center">
            <div className="flex w-full items-center">
              <div className={clsx("h-0.5 flex-1 transition-colors duration-500", i === 0 ? "invisible" : n <= reached ? "bg-brand-500" : "bg-slate-200")} />
              <span className={clsx("flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                done ? "bg-brand-600 text-white" : current ? "bg-white text-brand-700 ring-2 ring-brand-600" : "bg-slate-100 text-slate-400")}>
                {done ? <Check className="h-3.5 w-3.5" /> : n}
              </span>
              <div className={clsx("h-0.5 flex-1", i === STEPS.length - 1 ? "invisible" : n < reached ? "bg-brand-500" : "bg-slate-200")} />
            </div>
            <span className={clsx("mt-1.5 text-[11px] leading-tight sm:text-xs", n <= reached ? "font-medium text-slate-700" : "text-slate-400")}>{name}</span>
          </li>
        );
      })}
    </ol>
  );
}

export default function MyApplications() {
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["applications", "mine"], queryFn: applicationsApi.mine, refetchInterval: 10_000 });
  const qc = useQueryClient();
  if (isLoading) return <><PageHeader title="My applications" subtitle="Track where each application is in the process." /><ListSkeleton rows={3} /></>;
  if (error) return <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />;

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title="My applications" subtitle="Track where each application is in the process." />
      {!!data?.length && (
        <p className="mb-4 text-sm text-slate-500">
          {data.length} application{data.length === 1 ? "" : "s"}
          {data.some((a) => a.can_start_interview) && <> · <b className="text-brand-700">{data.filter((a) => a.can_start_interview).length} interview to do</b></>}
          {data.some((a) => a.shortlisted) && <> · <b className="text-emerald-700">{data.filter((a) => a.shortlisted).length} shortlisted</b></>}
        </p>
      )}
      {!data?.length ? (
        <EmptyState title="No applications yet" text="Browse open jobs and apply with your resume."
          action={<Link to="/jobs"><Button>Browse jobs</Button></Link>} />
      ) : (
        <div className="space-y-3">
          {data.map((app) => (
            <Card key={app.id} className="p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h2 className="text-[16px] font-semibold text-slate-900">{app.job_title}</h2>
                  <p className="text-xs text-slate-500">Applied {fmtDate(app.applied_at)} · Last update {fmtDate(app.updated_at)}</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={app.shortlisted ? "green" : app.can_start_interview ? "brand" : "gray"}>{app.status_label}</Badge>
                  {app.job_status === "closed" && <Badge>Position closed</Badge>}
                </div>
              </div>
              <Tracker app={app} />
              {app.reason && (
                <div className="mt-5 border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
                  <b>Why:</b> {app.reason}
                </div>
              )}
              {app.shortlisted && (
                <div className="mt-5 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
                  <span><b>Good news: you've been shortlisted.</b> The recruiter will contact you by email about the next steps.</span>
                </div>
              )}
              {app.can_start_interview && app.interview_session_id && (
                <div className="mt-5 flex flex-col gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-sm text-slate-700">
                    {app.interview_status === "in_progress" ? "You have an unfinished interview. Continue where you left off." : "You're invited to a short AI voice interview. You'll need a microphone."}
                  </p>
                  <Link to={`/interview/${app.interview_session_id}`} {...prefetchProps(qc, `/interview/${app.interview_session_id}`)}>
                    <Button className="w-full sm:w-auto">{app.interview_status === "in_progress" ? "Continue interview" : "Start interview"}</Button>
                  </Link>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
