import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Printer, RefreshCw, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { Link, useParams } from "react-router-dom";
import { errorMessage, fetchBlobUrl } from "../../api/client";
import { applicationsApi } from "../../api/endpoints";
import type { ApplicationDetail, Decision } from "../../api/types";
import { Disclaimer } from "../../components/Disclaimer";
import {
  Answer, AnswerChart, CandidateHeader, EventTimeline, IntegrityCharts, IntegritySummary, Mismatches, RequirementList,
  ScoreBadge, ScoreOverview, SkillMatch, Snapshots,
} from "../../components/report";
import { Badge, Button, ConfirmDialog, ErrorState, FullPageSpinner, Panel, Tabs } from "../../components/ui";
import { DECISION_TONE, STAGE_LABEL, STAGE_TONE, capitalize, fmtDate, fmtScore } from "../../lib/format";

type Tab = "overview" | "interview" | "integrity" | "resume";

export default function CandidateDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["application", id], queryFn: () => applicationsApi.detail(id!),
    refetchInterval: (query) => (["submitted", "under_review"].includes(query.state.data?.stage ?? "") ? 3000 : false) });
  const [tab, setTab] = useState<Tab>("overview");
  const [confirmReject, setConfirmReject] = useState(false);
  const [confirmInvite, setConfirmInvite] = useState(false);
  const [confirmDevice, setConfirmDevice] = useState(false);

  const updated = (d: ApplicationDetail) => {
    qc.setQueryData(["application", id], d);
    qc.invalidateQueries({ queryKey: ["candidates"] });
    qc.invalidateQueries({ queryKey: ["stats"] });
    qc.invalidateQueries({ queryKey: ["overview"] });
  };

  const decide = useMutation({
    mutationFn: ({ decision, notes }: { decision: Decision; notes: string | null }) => applicationsApi.decide(id!, decision, notes),
    onSuccess: (d, vars) => {
      updated(d);
      toast.success(vars.notes !== null ? "Notes saved" : `Marked as ${d.decision}`);
      setConfirmReject(false);
    },
    onError: (err) => toast.error(errorMessage(err)),
  });
  const invite = useMutation({
    mutationFn: () => applicationsApi.invite(id!),
    onSuccess: (d) => { updated(d); toast.success("Interview invitation sent"); setConfirmInvite(false); },
    onError: (err) => toast.error(errorMessage(err)),
  });
  const release = useMutation({
    mutationFn: () => applicationsApi.releaseDevice(id!),
    onSuccess: (d) => { updated(d); toast.success("The candidate can now continue on a new device"); setConfirmDevice(false); },
    onError: (err) => toast.error(errorMessage(err)),
  });
  const rescreen = useMutation({
    mutationFn: () => applicationsApi.rescreen(id!),
    onSuccess: () => { toast.success("Screening restarted"); setTimeout(() => qc.invalidateQueries({ queryKey: ["application", id] }), 1500); },
    onError: (err) => toast.error(errorMessage(err)),
  });

  // Opening a candidate marks them as seen, so the lists drop the "New" badge.
  const loaded = Boolean(q.data);
  useEffect(() => {
    if (!loaded) return;
    qc.invalidateQueries({ queryKey: ["candidates"] });
    qc.invalidateQueries({ queryKey: ["overview"] });
  }, [loaded, id, qc]);

  if (q.isLoading) return <FullPageSpinner />;
  if (q.error || !q.data) return <ErrorState message={errorMessage(q.error)} onRetry={() => q.refetch()} />;
  const d = q.data;
  const iv = d.interview;
  const report = iv?.integrity ?? null;

  return (
    <>
      <Link to={`/recruiter/jobs/${d.job_id}`} className="mb-3 inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-900">← {d.job_title}</Link>

      <div className="card mb-5 p-5 sm:p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <CandidateHeader d={d} />
          <ScoreBadge d={d} />
        </div>
        <div className="mt-5 flex flex-col gap-3 border-t border-slate-100 pt-4 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <Badge tone={STAGE_TONE[d.stage]}>{STAGE_LABEL[d.stage]}</Badge>
            <Badge tone={DECISION_TONE[d.decision]}>{capitalize(d.decision)}</Badge>
            {d.archived && <Badge>Archived (job closed)</Badge>}
            <span>Applied {fmtDate(d.applied_at)}</span>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link to={`/recruiter/candidates/${d.candidate.id}`}><Button variant="ghost" size="sm"><UserRound className="h-4 w-4" /> Full profile</Button></Link>
            <Link to={`/recruiter/applications/${d.id}/report`} target="_blank"><Button variant="ghost" size="sm"><Printer className="h-4 w-4" /> Print report</Button></Link>
            <Button size="sm" variant={d.decision === "shortlisted" ? "success" : "secondary"} aria-pressed={d.decision === "shortlisted"}
              loading={decide.isPending && decide.variables?.decision === "shortlisted"}
              onClick={() => decide.mutate({ decision: d.decision === "shortlisted" ? "pending" : "shortlisted", notes: null })}>
              {d.decision === "shortlisted" ? "Shortlisted" : "Shortlist"}
            </Button>
            <Button size="sm" variant={d.decision === "rejected" ? "danger" : "secondary"} aria-pressed={d.decision === "rejected"}
              onClick={() => (d.decision === "rejected" ? decide.mutate({ decision: "pending", notes: null }) : setConfirmReject(true))}>
              {d.decision === "rejected" ? "Rejected" : "Reject"}
            </Button>
          </div>
        </div>
      </div>

      <Disclaimer />
      <Notices d={d} onInvite={() => setConfirmInvite(true)} onRescreen={() => rescreen.mutate()} rescreening={rescreen.isPending} />

      <Tabs value={tab} onChange={setTab} tabs={[
        { value: "overview", label: "Overview" },
        { value: "interview", label: "Interview", count: iv?.responses.length },
        { value: "integrity", label: "Integrity", count: report?.strikes, highlight: report?.level === "high" },
        { value: "resume", label: "Resume & notes" },
      ]} />

      <div className="mt-5">
        {tab === "overview" && (
          <div className="grid gap-5 lg:grid-cols-3">
            <Panel title="Score breakdown" className="lg:col-span-2"><ScoreOverview d={d} /></Panel>
            <Panel title="Minimum requirements" subtitle="Checked against the resume">
              <RequirementList d={d} />
              {d.mismatches.length > 0 && <div className="mt-3"><Mismatches items={d.mismatches} /></div>}
            </Panel>
            <Panel title="Required skills" className="lg:col-span-2"><SkillMatch d={d} /></Panel>
            <Panel title="AI summary">
              <p className="text-sm leading-relaxed text-slate-700">{d.parsed_resume?.summary ?? "Not available yet."}</p>
            </Panel>
          </div>
        )}

        {tab === "interview" && (
          !iv ? (
            <Panel title="Voice interview">
              <p className="text-sm text-slate-500">{d.stage === "not_qualified" ? (d.review_reason ? `Not invited. ${d.review_reason}.` : "Not invited: the resume score was below the job's threshold.") : "No interview yet."}</p>
            </Panel>
          ) : (
            <div className="space-y-5">
              <Panel title="Answer scores"
                subtitle={<>Status: {iv.status.replace("_", " ")} · {iv.responses.length}/{iv.total_questions} answered{d.scores?.interview_score != null && <> · Interview score {fmtScore(d.scores.interview_score)}/30</>}</>}>
                {iv.responses.length ? <AnswerChart responses={iv.responses} /> : (
                  <div>
                    <p className="mb-2 text-sm text-slate-500">No answers yet. Questions prepared for this candidate:</p>
                    <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-700">{iv.questions.map((x) => <li key={x.index}>{x.text}</li>)}</ol>
                  </div>
                )}
              </Panel>
              {iv.responses.map((r) => <Answer key={r.question_index} appId={d.id} r={r} />)}
            </div>
          )
        )}

        {tab === "integrity" && (
          !report ? (
            <Panel title="Integrity"><p className="text-sm text-slate-500">The interview has not started yet.</p></Panel>
          ) : (
            <div className="space-y-5">
              <IntegritySummary report={report} />
              {iv?.device_locked && iv.status !== "completed" && (
                <div className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 sm:flex-row sm:items-center sm:justify-between">
                  <span>The interview is locked to the device the candidate started on. If their device broke, you can let them continue on another one.</span>
                  <Button size="sm" variant="secondary" onClick={() => setConfirmDevice(true)}>Allow a new device</Button>
                </div>
              )}
              <Panel title="Flags and attention"><IntegrityCharts report={report} questions={iv?.total_questions ?? 0} /></Panel>
              <div className="grid gap-5 lg:grid-cols-2">
                <Panel title="Timeline"><div className="max-h-80 overflow-y-auto"><EventTimeline report={report} /></div></Panel>
                <Panel title="Webcam photos" subtitle="Red border: taken when something was flagged">
                  <Snapshots appId={d.id} report={report} />
                  <p className="mt-3 text-[11px] text-slate-500">Tracking runs in the candidate's browser. Lighting, glasses or a poor camera can cause wrong flags, so check the photos and recordings before deciding.</p>
                </Panel>
              </div>
            </div>
          )
        )}

        {tab === "resume" && <ResumeTab d={d} onSave={(notes) => decide.mutate({ decision: d.decision, notes })} saving={decide.isPending && decide.variables?.notes !== null} />}
      </div>

      <ConfirmDialog open={confirmInvite} title="Invite to the voice interview?"
        message={<><b>{d.candidate.full_name}</b> gets an email invitation and can start the interview right away.</>}
        confirmLabel="Send invitation" loading={invite.isPending} onConfirm={() => invite.mutate()} onCancel={() => setConfirmInvite(false)} />
      <ConfirmDialog open={confirmReject} title="Mark as rejected?"
        message={<>This records your decision for <b>{d.candidate.full_name}</b>. You can change it later.</>}
        confirmLabel="Mark rejected" danger loading={decide.isPending}
        onConfirm={() => decide.mutate({ decision: "rejected", notes: null })} onCancel={() => setConfirmReject(false)} />
      <ConfirmDialog open={confirmDevice} title="Allow a new device?"
        message={<>The next device <b>{d.candidate.full_name}</b> opens the interview on becomes the only one allowed. This is recorded in the integrity log.</>}
        confirmLabel="Allow new device" loading={release.isPending} onConfirm={() => release.mutate()} onCancel={() => setConfirmDevice(false)} />
    </>
  );
}

function Notices({ d, onInvite, onRescreen, rescreening }: { d: ApplicationDetail; onInvite: () => void; onRescreen: () => void; rescreening: boolean }) {
  const iv = d.interview;
  const items = [];
  if (d.stage === "submitted" || d.stage === "under_review") {
    items.push(
      <div key="screen" className="flex items-center gap-2 rounded-lg border border-neutral-200 bg-neutral-50 px-4 py-3 text-sm text-neutral-800">
        <RefreshCw className="h-4 w-4 animate-spin" /> The AI is reading this resume. This page updates by itself.
      </div>,
    );
  }
  if ((d.stage === "not_qualified" || d.stage === "screening_failed") && !d.archived) {
    items.push(
      <div key="invite" className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 sm:flex-row sm:items-center sm:justify-between">
        <span>{d.stage === "not_qualified" ? (d.review_reason ?? "Scored below the job's threshold, so not invited automatically.") : "The resume could not be read automatically."} You can still invite them.</span>
        <Button size="sm" onClick={onInvite}>Invite to interview</Button>
      </div>,
    );
  }
  if (d.needs_manual_review) {
    items.push(
      <div key="review" className="flex flex-col gap-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 sm:flex-row sm:items-center sm:justify-between">
        <span><b>Needs manual review:</b> {d.review_reason}</span>
        {d.stage === "screening_failed" && <Button size="sm" variant="secondary" loading={rescreening} onClick={onRescreen}>Re-run screening</Button>}
      </div>,
    );
  }
  if (iv?.issue_reported) {
    items.push(
      <div key="issue" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
        <b>Candidate reported a technical problem:</b> <span className="whitespace-pre-line">{iv.issue_text}</span>
      </div>,
    );
  }
  if (iv?.responses.some((r) => r.pending)) {
    items.push(
      <div key="pending" className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
        Some answers are waiting for the AI to score them. They are scored automatically when the AI is free again.
      </div>,
    );
  }
  return items.length ? <div className="mb-5 space-y-2">{items}</div> : null;
}

function ResumeTab({ d, onSave, saving }: { d: ApplicationDetail; onSave: (notes: string) => void; saving: boolean }) {
  const [notes, setNotes] = useState(d.notes ?? "");
  const [opening, setOpening] = useState(false);
  useEffect(() => setNotes(d.notes ?? ""), [d.notes]);
  const p = d.parsed_resume;
  const s = d.scores;

  const openPdf = async () => {
    setOpening(true);
    const win = window.open("", "_blank");
    try {
      const url = await fetchBlobUrl(`/applications/${d.id}/resume`);
      if (win) win.location.href = url; else window.location.href = url;
    } catch (err) {
      win?.close();
      toast.error(errorMessage(err));
    } finally {
      setOpening(false);
    }
  };

  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <div className="space-y-5 lg:col-span-2">
        <Panel title="What the AI found in the resume"
          action={<Button size="sm" variant="secondary" loading={opening} onClick={openPdf}><FileText className="h-4 w-4" /> Open PDF</Button>}>
          {p ? (
            <>
              <dl className="grid gap-4 text-sm sm:grid-cols-3">
                <div><dt className="text-xs text-slate-500">Experience</dt><dd className="mt-0.5 font-medium">{fmtScore(p.years_experience)} years</dd></div>
                <div><dt className="text-xs text-slate-500">Education</dt><dd className="mt-0.5 font-medium">{p.education || "—"}</dd></div>
                <div><dt className="text-xs text-slate-500">Certifications</dt><dd className="mt-0.5 font-medium">{p.certifications.length ? p.certifications.join(", ") : "—"}</dd></div>
              </dl>
              {p.skills.length > 0 && <div className="mt-4 flex flex-wrap gap-1.5">{p.skills.map((k) => <Badge key={k}>{k}</Badge>)}</div>}
              {s?.resume_reasoning && <p className="mt-4 whitespace-pre-line rounded-lg bg-slate-50 p-3 text-sm text-slate-700">{s.resume_reasoning}</p>}
            </>
          ) : <p className="text-sm text-slate-500">Not read yet.</p>}
        </Panel>
        {d.form_answers.length > 0 && (
          <Panel title="Answers to the job's questions">
            <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
              {d.form_answers.map((a) => (
                <div key={a.id} className="min-w-0">
                  <dt className="text-xs text-slate-500">{a.label}</dt>
                  <dd className="mt-0.5 break-words text-sm font-medium text-slate-900">
                    {/^https?:\/\//.test(a.answer) ? <a href={a.answer} target="_blank" rel="noopener noreferrer nofollow" className="link">{a.answer}</a> : a.answer}
                  </dd>
                </div>
              ))}
            </dl>
          </Panel>
        )}
      </div>
      <Panel title="Private notes" subtitle="Only you can see these.">
        <textarea className="input" rows={8} maxLength={5000} value={notes} onChange={(e) => setNotes(e.target.value)} aria-label="Private notes" />
        <Button className="mt-3 w-full" variant="secondary" loading={saving} disabled={notes === (d.notes ?? "")} onClick={() => onSave(notes)}>Save notes</Button>
      </Panel>
    </div>
  );
}
