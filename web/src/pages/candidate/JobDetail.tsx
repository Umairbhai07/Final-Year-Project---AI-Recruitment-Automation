import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { CheckCircle2, FileText, X, XCircle } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import toast from "react-hot-toast";
import { Link, useParams } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { applicationsApi, jobsApi, profileApi } from "../../api/endpoints";
import type { ApplyResult, Job } from "../../api/types";
import { ApplyFields } from "../../components/ApplyFields";
import { checkAnswers, type Answers } from "../../lib/answers";
import { Badge, Button, Card, ErrorState, FullPageSpinner, Spinner } from "../../components/ui";
import { EDUCATION_LABEL, fmtDate } from "../../lib/format";

const MAX_BYTES = 5 * 1024 * 1024;

function checkFile(file: File): string | null {
  const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
  if (!isPdf) return "Please choose a PDF file.";
  if (file.size > MAX_BYTES) return "The file is larger than 5 MB.";
  if (file.size === 0) return "The file is empty.";
  return null;
}

export default function JobDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { data: job, isLoading, error } = useQuery({ queryKey: ["job", id], queryFn: () => jobsApi.get(id!) });
  const profile = useQuery({ queryKey: ["profile", "me"], queryFn: profileApi.me });
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState(0);
  const [answers, setAnswers] = useState<Answers>({});
  const [answerErrors, setAnswerErrors] = useState<Record<string, string>>({});
  const inputRef = useRef<HTMLInputElement>(null);

  const apply = useMutation({
    // with no file chosen, the server uses the resume saved in the profile
    mutationFn: () => applicationsApi.apply(id!, file, answers, setProgress),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["job", id] });
      qc.invalidateQueries({ queryKey: ["applications"] });
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  const pick = (f: File | undefined) => {
    if (!f) return;
    const problem = checkFile(f);
    setFileError(problem);
    setFile(problem ? null : f);
  };

  const setAnswer = (qid: string, value: string) => {
    setAnswers((a) => ({ ...a, [qid]: value }));
    setAnswerErrors((e) => {
      if (!e[qid]) return e;
      const next = { ...e };
      delete next[qid];
      return next;
    });
  };

  const submit = () => {
    const problems = checkAnswers(job?.application_form ?? [], answers);
    setAnswerErrors(problems);
    if (Object.keys(problems).length) {
      document.getElementById(`q-${Object.keys(problems)[0]}`)?.focus();
      toast.error("Please answer the required questions.");
      return;
    }
    apply.mutate();
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    pick(e.dataTransfer.files?.[0]);
  };

  if (isLoading) return <FullPageSpinner />;
  if (error || !job) return <ErrorState message={errorMessage(error, "This job is no longer available.")} />;

  if (apply.isSuccess && apply.data) return <ApplyOutcome result={apply.data} jobTitle={job.title} />;

  const deadlinePassed = job.deadline ? new Date(job.deadline) < new Date(new Date().toDateString()) : false;
  const elig = job.eligibility;
  const p = profile.data;
  const canApply = !!elig?.eligible;

  return (
    <div className="mx-auto max-w-6xl">
      <Link to="/jobs" className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-900">← All jobs</Link>
      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <Card className="p-6 sm:p-8">
          <h1 className="text-2xl font-bold text-slate-900 sm:text-[28px]">{job.title}</h1>
          {job.company && <p className="mt-0.5 text-slate-500">{job.company}</p>}
          <dl className="mt-5 grid grid-cols-2 gap-4 border-y border-slate-100 py-4 text-sm sm:grid-cols-4">
            <div><dt className="text-xs text-slate-500">Degree</dt><dd className="font-medium">{job.education_level === "none" ? "Any" : `${EDUCATION_LABEL[job.education_level]}+`}</dd></div>
            <div><dt className="text-xs text-slate-500">Experience</dt><dd className="font-medium">{job.min_experience_years ? `${job.min_experience_years}+ years` : "None needed"}</dd></div>
            <div><dt className="text-xs text-slate-500">CGPA</dt><dd className="font-medium">{job.min_cgpa ? `${job.min_cgpa.toFixed(2)}+` : "No minimum"}</dd></div>
            <div><dt className="text-xs text-slate-500">Deadline</dt><dd className="font-medium">{job.deadline ? fmtDate(job.deadline) : "None"}</dd></div>
          </dl>
          <h2 className="mt-6 text-sm font-semibold text-slate-900">Skills</h2>
          <div className="mt-2 flex flex-wrap gap-1.5">{job.required_skills.map((s) => <Badge key={s} tone="brand">{s}</Badge>)}</div>
          <h2 className="mt-6 text-sm font-semibold text-slate-900">About the role</h2>
          <p className="mt-2 whitespace-pre-line text-[15px] leading-relaxed text-slate-700">{job.description}</p>
        </Card>

        <div className="space-y-4 lg:sticky lg:top-6 lg:self-start">
          <Requirements job={job} />

          <Card className="p-5">
            <h2 className="text-base font-semibold text-slate-900">Apply</h2>
            {job.has_applied ? (
              <div className="mt-3 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">
                You've already applied. <Link to="/applications" className="font-medium underline">Track your application</Link>.
              </div>
            ) : deadlinePassed ? (
              <p className="mt-3 text-sm text-slate-500">The deadline for this job has passed.</p>
            ) : elig && !elig.profile_complete ? (
              <div className="mt-3 space-y-3 text-sm">
                <p className="text-slate-600">Finish your profile first. Still needed: {p?.missing.join(", ") || "a few details"}.</p>
                <Link to="/profile"><Button className="w-full">Complete my profile</Button></Link>
              </div>
            ) : !canApply ? (
              <p className="mt-3 text-sm text-slate-600">You can't apply to this job right now.</p>
            ) : (
              <>
                {job.application_form?.length > 0 && (
                  <div className="mt-4">
                    <p className="mb-3 text-sm text-slate-500">A few questions from the recruiter:</p>
                    <ApplyFields questions={job.application_form} answers={answers} errors={answerErrors} onChange={setAnswer} />
                  </div>
                )}
                <div className="mt-4">
                  <p className="label">Resume</p>
                  {file ? (
                    <div className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2.5 text-sm">
                      <span className="flex min-w-0 items-center gap-2"><FileText className="h-4 w-4 shrink-0 text-slate-400" /><span className="truncate">{file.name}</span></span>
                      <button onClick={() => setFile(null)} aria-label="Use my profile resume instead" className="rounded p-0.5 text-slate-500 hover:bg-slate-100"><X className="h-3.5 w-3.5" /></button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-700">
                      <FileText className="h-4 w-4 shrink-0 text-slate-400" />
                      <span className="truncate">{p?.resume_filename ?? "Profile resume"}</span>
                      <span className="ml-auto shrink-0 text-xs text-slate-500">from profile</span>
                    </div>
                  )}
                  <div
                    role="button" tabIndex={0}
                    onClick={() => inputRef.current?.click()}
                    onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
                    onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={onDrop}
                    className={clsx("mt-2 cursor-pointer rounded-lg border border-dashed px-3 py-2.5 text-center text-xs transition",
                      dragging ? "border-brand-500 bg-brand-50 text-brand-700" : "border-slate-300 text-slate-500 hover:border-brand-400")}
                  >
                    Use a different PDF for this job (optional)
                    <input ref={inputRef} type="file" accept="application/pdf,.pdf" className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
                  </div>
                  {fileError && <p className="field-error" role="alert">{fileError}</p>}
                </div>
                {apply.isPending && (
                  <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full bg-brand-600 transition-all" style={{ width: `${progress}%` }} /></div>
                )}
                <Button className="mt-5 w-full" loading={apply.isPending} onClick={submit}>Submit application</Button>
              </>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

function Requirements({ job }: { job: Job }) {
  const rules = [
    job.education_level !== "none" && `${EDUCATION_LABEL[job.education_level]} or higher`,
    job.min_experience_years > 0 && `${job.min_experience_years}+ years of experience`,
    !!job.min_cgpa && `CGPA ${job.min_cgpa.toFixed(2)} or higher`,
  ].filter(Boolean) as string[];
  if (!rules.length) return null;
  return (
    <Card className="p-5">
      <h2 className="text-base font-semibold text-slate-900">Minimum requirements</h2>
      <ul className="mt-3 space-y-2">
        {rules.map((r) => (
          <li key={r} className="flex items-start gap-2.5 text-sm text-slate-800">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" /> {r}
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-slate-500">We check these against your resume when you apply.</p>
    </Card>
  );
}

/** Right after applying: invited, not selected (with the reason), or still being checked. */
function ApplyOutcome({ result, jobTitle }: { result: ApplyResult; jobTitle: string }) {
  const pending = result.stage === "submitted" || result.stage === "under_review";
  const [started] = useState(() => Date.now());
  // Where screening runs after the answer (local development), ask until it is done, for up to a minute.
  const mine = useQuery({
    queryKey: ["applications", "mine"],
    queryFn: applicationsApi.mine,
    enabled: pending,
    refetchInterval: (q) => {
      const a = q.state.data?.find((x) => x.id === result.id);
      const waiting = !a || a.status_label === "Submitted" || a.status_label === "Under review";
      return waiting && Date.now() - started < 60_000 ? 2000 : false;
    },
  });
  const latest = mine.data?.find((x) => x.id === result.id);
  const label = latest?.status_label ?? result.status_label;
  const reason = latest?.reason ?? result.reason;
  const checking = pending && (!latest || label === "Submitted" || label === "Under review") && Date.now() - started < 60_000;

  const icon = checking ? <Spinner className="mx-auto h-12 w-12" />
    : label === "Not selected" ? <XCircle className="mx-auto h-14 w-14 text-neutral-400" />
    : <CheckCircle2 className="mx-auto h-14 w-14 text-neutral-950" />;
  return (
    <Card className="mx-auto max-w-lg p-8 text-center">
      {icon}
      {checking ? (
        <>
          <h1 className="mt-4 text-2xl font-bold">Checking your application…</h1>
          <p className="mt-2 text-slate-600">We're reading your resume for <b>{jobTitle}</b>. This usually takes a few seconds.</p>
        </>
      ) : label === "Not selected" ? (
        <>
          <h1 className="mt-4 text-2xl font-bold">You don't meet this job's criteria</h1>
          <p className="mt-2 text-slate-600">Your application for <b>{jobTitle}</b> was received, but it can't go forward.</p>
          {reason && <p className="mt-4 border border-slate-200 bg-slate-50 p-3 text-left text-sm text-slate-700"><b>Reason:</b> {reason}</p>}
          <p className="mt-3 text-xs text-slate-500">The recruiter can still see your application.</p>
        </>
      ) : label === "Interview invited" ? (
        <>
          <h1 className="mt-4 text-2xl font-bold">You're invited to the interview</h1>
          <p className="mt-2 text-slate-600">Your resume matches <b>{jobTitle}</b>. Start the short voice interview from My applications.</p>
        </>
      ) : (
        <>
          <h1 className="mt-4 text-2xl font-bold">Application submitted</h1>
          <p className="mt-2 text-slate-600">Thanks for applying to <b>{jobTitle}</b>. The recruiter is reviewing it. Track it in My applications.</p>
        </>
      )}
      <div className="mt-6 flex flex-col justify-center gap-2 sm:flex-row">
        <Link to="/applications"><Button className="w-full">My applications</Button></Link>
        <Link to="/jobs"><Button variant="secondary" className="w-full">Browse more jobs</Button></Link>
      </div>
    </Card>
  );
}
