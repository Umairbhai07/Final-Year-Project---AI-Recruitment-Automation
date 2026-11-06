import { useQuery } from "@tanstack/react-query";
import { Printer } from "lucide-react";
import { useEffect, type ReactNode } from "react";
import { useParams } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { applicationsApi } from "../../api/endpoints";
import {
  Answer, AnswerChart, CandidateHeader, EventTimeline, IntegrityCharts, IntegritySummary, Mismatches, RequirementList,
  ScoreBadge, ScoreOverview, SkillMatch,
} from "../../components/report";
import { Badge, Button, ErrorState, FullPageSpinner } from "../../components/ui";
import { DECISION_TONE, STAGE_LABEL, STAGE_TONE, capitalize, fmtDate } from "../../lib/format";

/** A one-page style report of a candidate for printing or saving as PDF from the browser. */
export default function CandidateReport() {
  const { id } = useParams();
  const q = useQuery({ queryKey: ["application", id], queryFn: () => applicationsApi.detail(id!) });

  useEffect(() => {
    if (!q.data) return;
    document.title = `${q.data.candidate.full_name} – ${q.data.job_title}`;
    const t = setTimeout(() => window.print(), 900); // give the charts a moment to draw
    return () => clearTimeout(t);
  }, [q.data]);

  if (q.isLoading) return <div className="p-8"><FullPageSpinner /></div>;
  if (q.error || !q.data) return <div className="p-8"><ErrorState message={errorMessage(q.error)} /></div>;
  const d = q.data;
  const iv = d.interview;

  return (
    <div className="min-h-screen bg-white">
      <div className="mx-auto max-w-[900px] px-8 py-8 print:px-0 print:py-0">
        <div className="no-print mb-6 flex justify-end"><Button onClick={() => window.print()}><Printer className="h-4 w-4" /> Print or save as PDF</Button></div>

        <header className="flex items-start justify-between gap-6 border-b border-slate-200 pb-5">
          <CandidateHeader d={d} compact />
          <ScoreBadge d={d} />
        </header>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <span className="font-medium text-slate-700">{d.job_title}</span>
          <Badge tone={STAGE_TONE[d.stage]}>{STAGE_LABEL[d.stage]}</Badge>
          <Badge tone={DECISION_TONE[d.decision]}>{capitalize(d.decision)}</Badge>
          <span>Applied {fmtDate(d.applied_at)} · Report made {fmtDate(new Date().toISOString())}</span>
        </div>

        <Section title="Score breakdown"><ScoreOverview d={d} height={200} /></Section>
        <div className="grid grid-cols-2 gap-6">
          <Section title="Minimum requirements">
            <RequirementList d={d} />
            {d.mismatches.length > 0 && <div className="mt-3"><Mismatches items={d.mismatches} /></div>}
          </Section>
          <Section title="Required skills"><SkillMatch d={d} /></Section>
        </div>
        {d.parsed_resume?.summary && <Section title="AI summary"><p className="text-sm leading-relaxed text-slate-700">{d.parsed_resume.summary}</p></Section>}

        {iv && iv.responses.length > 0 && (
          <>
            <Section title="Interview answers"><AnswerChart responses={iv.responses} /></Section>
            <div className="space-y-3">{iv.responses.map((r) => <Answer key={r.question_index} appId={d.id} r={r} printable />)}</div>
          </>
        )}
        {iv?.integrity && (
          <Section title="Interview integrity">
            <IntegritySummary report={iv.integrity} />
            <div className="mt-4"><IntegrityCharts report={iv.integrity} questions={iv.total_questions} /></div>
            <div className="mt-4"><EventTimeline report={iv.integrity} /></div>
          </Section>
        )}
        {d.notes && <Section title="Recruiter notes"><p className="whitespace-pre-line text-sm text-slate-700">{d.notes}</p></Section>}
        <p className="mt-8 border-t border-slate-200 pt-3 text-[11px] text-slate-400">AI scores are a guide. Final hiring decisions are made by the recruiter.</p>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-6 break-inside-avoid">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">{title}</h2>
      {children}
    </section>
  );
}
