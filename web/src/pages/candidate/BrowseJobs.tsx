import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, GraduationCap, Search, Briefcase } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { jobsApi, profileApi } from "../../api/endpoints";
import type { Job } from "../../api/types";
import { Badge, EmptyState, ErrorState, Skeleton, Spinner } from "../../components/ui";
import { prefetchProps } from "../../lib/prefetch";
import { EDUCATION_LABEL, fmtDate } from "../../lib/format";

export default function BrowseJobs() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebounced(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["jobs", "browse", debounced],
    queryFn: () => jobsApi.list(debounced),
    placeholderData: (prev) => prev,
  });
  const profile = useQuery({ queryKey: ["profile", "me"], queryFn: profileApi.me });
  const jobs = data ?? [];

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-[26px]">Find jobs</h1>
        <p className="mt-1 text-sm text-slate-500">Each job lists its minimum degree, experience and CGPA. We check them against your resume when you apply.</p>
      </div>

      {profile.data && !profile.data.complete && (
        <div className="mb-5 flex flex-wrap items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <span className="font-medium">Your profile is {profile.data.completion}% complete.</span>
          <span className="text-amber-800">You can apply once it is finished.</span>
          <Link to="/profile" className="ml-auto font-semibold text-amber-900 underline">Complete profile</Link>
        </div>
      )}

      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input className="input pl-10 pr-10" placeholder="Search by title or skill" value={search}
            onChange={(e) => setSearch(e.target.value)} aria-label="Search jobs" />
          {isFetching && <Spinner className="absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2" />}
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-32 rounded-xl" />)}</div>
      ) : error ? (
        <ErrorState message={errorMessage(error)} onRetry={() => refetch()} />
      ) : !jobs.length ? (
        <EmptyState title={debounced ? "No jobs match your search" : "No open jobs right now"}
          text={debounced ? "Try another title or skill." : "Check back soon."} />
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-slate-500">{jobs.length} job{jobs.length === 1 ? "" : "s"}{debounced && <> for “{debounced}”</>}</p>
          {jobs.map((job) => <JobRow key={job.id} job={job} prefetch={prefetchProps(qc, `/jobs/${job.id}`)} />)}
        </div>
      )}
    </div>
  );
}

function JobRow({ job, prefetch }: { job: Job; prefetch: object }) {
  const e = job.eligibility;
  return (
    <Link to={`/jobs/${job.id}`} {...prefetch}
      className="card card-hover block p-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h2 className="text-[16px] font-semibold text-slate-900">{job.title}</h2>
          {job.company && <p className="text-sm text-slate-500">{job.company}</p>}
        </div>
        <div className="shrink-0">
          {job.has_applied ? (
            <Badge tone="green">Applied</Badge>
          ) : e && !e.profile_complete ? (
            <Badge tone="gray">Finish profile to apply</Badge>
          ) : null}
        </div>
      </div>
      <p className="mt-2 line-clamp-2 text-sm text-slate-600">{job.description}</p>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-slate-500">
        <span className="flex items-center gap-1"><GraduationCap className="h-3.5 w-3.5" />{job.education_level === "none" ? "Any education" : `${EDUCATION_LABEL[job.education_level]}+`}{job.min_cgpa ? `, CGPA ${job.min_cgpa.toFixed(1)}+` : ""}</span>
        <span className="flex items-center gap-1"><Briefcase className="h-3.5 w-3.5" />{job.min_experience_years ? `${job.min_experience_years}+ years` : "Freshers welcome"}</span>
        <span className="flex items-center gap-1"><CalendarDays className="h-3.5 w-3.5" />{job.deadline ? `Apply by ${fmtDate(job.deadline)}` : "No deadline"}</span>
        <span className="flex flex-wrap gap-1">
          {job.required_skills.slice(0, 5).map((s) => <span key={s} className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-600">{s}</span>)}
          {job.required_skills.length > 5 && <span className="px-1 text-slate-400">+{job.required_skills.length - 5}</span>}
        </span>
      </div>
    </Link>
  );
}
