import { useQuery } from "@tanstack/react-query";
import { FileText, Globe, Mail, MapPin, Phone } from "lucide-react";
import { useState } from "react";
import toast from "react-hot-toast";
import { Link, useNavigate, useParams } from "react-router-dom";
import { errorMessage, fetchBlobUrl } from "../../api/client";
import { profileApi } from "../../api/endpoints";
import { GithubIcon, LinkedinIcon } from "../../components/BrandIcons";
import { Avatar, Badge, Button, ErrorState, FullPageSpinner, Panel, ScoreChip } from "../../components/ui";
import { DECISION_TONE, STAGE_LABEL, STAGE_TONE, capitalize, fmtAgo, fmtDate } from "../../lib/format";

/** A candidate's profile as a recruiter sees it, with every job they applied to at this recruiter (not other companies). */
export default function CandidateProfile() {
  const { candidateId } = useParams();
  const navigate = useNavigate();
  const q = useQuery({ queryKey: ["candidate", candidateId], queryFn: () => profileApi.candidate(candidateId!) });
  const [opening, setOpening] = useState(false);

  if (q.isLoading) return <FullPageSpinner />;
  if (q.error || !q.data) return <ErrorState message={errorMessage(q.error)} onRetry={() => q.refetch()} />;
  const { profile: p, applications, member_since } = q.data;

  const openResume = async () => {
    setOpening(true);
    const win = window.open("", "_blank");
    try {
      const url = await fetchBlobUrl(`/candidates/${candidateId}/resume`);
      if (win) win.location.href = url; else window.location.href = url;
    } catch (err) {
      win?.close();
      toast.error(errorMessage(err));
    } finally {
      setOpening(false);
    }
  };

  const links = [
    p.linkedin_url && { href: p.linkedin_url, label: "LinkedIn", icon: <LinkedinIcon /> },
    p.github_url && { href: p.github_url, label: "GitHub", icon: <GithubIcon /> },
    p.portfolio_url && { href: p.portfolio_url, label: "Portfolio", icon: <Globe className="h-4 w-4" /> },
  ].filter(Boolean) as { href: string; label: string; icon: JSX.Element }[];

  return (
    <div className="mx-auto max-w-5xl">
      <button type="button" onClick={() => navigate(-1)} className="mb-3 inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-900">← Back</button>

      <div className="card mb-5 flex flex-col gap-5 p-6 sm:flex-row sm:items-center">
        <Avatar name={p.full_name} src={p.photo_url} size={104} />
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">{p.full_name}</h1>
          {p.headline && <p className="text-slate-600">{p.headline}</p>}
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-500">
            <span className="flex items-center gap-1.5"><Mail className="h-4 w-4" />{p.email}</span>
            {p.phone && <span className="flex items-center gap-1.5"><Phone className="h-4 w-4" />{p.phone}</span>}
            {p.city && <span className="flex items-center gap-1.5"><MapPin className="h-4 w-4" />{p.city}</span>}
            <span>Member since {fmtDate(member_since)}</span>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {links.map((l) => (
              <a key={l.label} href={l.href} target="_blank" rel="noopener noreferrer nofollow"
                className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 px-2.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50">{l.icon}{l.label}</a>
            ))}
            {p.has_resume && <Button size="sm" variant="secondary" loading={opening} onClick={openResume}><FileText className="h-4 w-4" /> Resume</Button>}
          </div>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <Panel title={`Applications to your jobs (${applications.length})`} bodyClassName="px-0 pb-2">
            <ul className="divide-y divide-slate-100">
              {applications.map((a) => (
                <li key={a.application_id}>
                  <Link to={`/recruiter/applications/${a.application_id}`} className="flex items-center gap-4 px-5 py-3 hover:bg-slate-50">
                    <div className="min-w-0 flex-1">
                      <div className="font-medium text-slate-900">{a.job_title}{a.job_status !== "active" && <span className="ml-2 text-xs font-normal capitalize text-slate-400">({a.job_status})</span>}</div>
                      <div className="text-xs text-slate-500">Applied {fmtDate(a.applied_at)}{a.last_activity && <> · {a.last_activity} {fmtAgo(a.last_activity_at)}</>}</div>
                      {a.mismatches.length > 0 && <div className="mt-0.5 text-xs text-amber-700">{a.mismatches[0]}</div>}
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      <Badge tone={STAGE_TONE[a.stage]}>{STAGE_LABEL[a.stage]}</Badge>
                      {a.decision !== "pending" && <Badge tone={DECISION_TONE[a.decision]}>{capitalize(a.decision)}</Badge>}
                    </div>
                    <ScoreChip value={a.composite_score} />
                  </Link>
                </li>
              ))}
            </ul>
          </Panel>
          {p.about && <Panel title="About"><p className="whitespace-pre-line text-sm leading-relaxed text-slate-700">{p.about}</p></Panel>}
          {p.experience.length > 0 && (
            <Panel title="Experience">
              <ul className="space-y-3">
                {p.experience.map((e, i) => (
                  <li key={i} className="flex justify-between gap-3 text-sm">
                    <span><b className="font-medium text-slate-900">{e.title}</b><span className="text-slate-500"> at {e.company}</span></span>
                    <span className="shrink-0 text-slate-500">{e.years} yr{e.years === 1 ? "" : "s"}</span>
                  </li>
                ))}
              </ul>
            </Panel>
          )}
        </div>
        <div className="space-y-5">
          {(p.highest_degree_label || p.institute || p.cgpa !== null || p.experience_years !== null) && <Panel title="Education">
            <dl className="space-y-2.5 text-sm">
              <Row label="Highest degree" value={p.highest_degree_label} />
              <Row label="Field" value={p.field_of_study} />
              <Row label="Institute" value={p.institute} />
              <Row label="CGPA" value={p.cgpa !== null ? `${p.cgpa.toFixed(2)} / 4.00` : null} />
              <Row label="Graduated" value={p.graduation_year ? String(p.graduation_year) : null} />
              <Row label="Experience" value={p.experience_years !== null ? `${p.experience_years} years` : null} />
            </dl>
          </Panel>}
          {p.skills.length > 0 && <Panel title="Skills"><div className="flex flex-wrap gap-1.5">{p.skills.map((s) => <Badge key={s}>{s}</Badge>)}</div></Panel>}
          <p className="px-1 text-xs text-slate-400">These details are what the candidate entered. Degree, experience and skills are read from the resume on each application.</p>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-900">{value || "—"}</dd>
    </div>
  );
}
