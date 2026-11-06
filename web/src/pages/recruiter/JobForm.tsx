import clsx from "clsx";
import { Briefcase, CalendarDays } from "lucide-react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { Link, useNavigate, useParams } from "react-router-dom";
import { z } from "zod";
import { errorMessage } from "../../api/client";
import { jobsApi } from "../../api/endpoints";
import type { FormQuestion, JobInput } from "../../api/types";
import { FormBuilder } from "../../components/FormBuilder";
import { DEFAULT_FORM } from "../../lib/formPresets";
import { TagInput } from "../../components/TagInput";
import { Field, FormSection, Segmented, Select, TextArea, TextInput } from "../../components/form";
import { Button, ErrorState, FullPageSpinner, PageHeader } from "../../components/ui";
import { EDUCATION_LABEL } from "../../lib/format";

const schema = z.object({
  title: z.string().trim().min(3, "Title must be at least 3 characters").max(200),
  description: z.string().trim().min(20, "Describe the role in at least 20 characters"),
  required_skills: z.array(z.string()).min(1, "Add at least one required skill").max(30),
  min_experience_years: z.coerce.number().int("Whole years only").min(0).max(40),
  education_level: z.enum(["none", "matric", "high_school", "diploma", "bachelors", "masters", "phd"]),
  // kept as text in the form ("" means no rule) and turned into a number when saving
  min_cgpa: z.string().refine((v) => v.trim() === "" || (Number(v) >= 0 && Number(v) <= 4), "CGPA is out of 4.0"),
  deadline: z.string().optional(),
  screening_threshold: z.coerce.number().int().min(0).max(70),
  num_questions: z.coerce.number().int().min(5).max(8),
  seconds_per_question: z.coerce.number().int().min(30, "At least 30 seconds").max(600, "At most 10 minutes"),
  think_seconds: z.coerce.number().int().min(5, "At least 5 seconds").max(60, "At most 60 seconds"),
  follow_up_questions: z.coerce.number().int().min(0).max(3),
  require_webcam: z.boolean(),
  application_form: z
    .array(z.custom<FormQuestion>())
    .max(15)
    .refine((qs) => qs.every((q) => q.label.trim().length >= 2), "Every question needs some text"),
});
type Form = z.infer<typeof schema>;

const DEFAULTS: Form = {
  title: "", description: "", required_skills: [], min_experience_years: 0, education_level: "bachelors", min_cgpa: "",
  deadline: "", screening_threshold: 40, num_questions: 6, seconds_per_question: 120, think_seconds: 15, follow_up_questions: 1, require_webcam: true, application_form: DEFAULT_FORM,
};

export default function JobForm() {
  const { id } = useParams();
  const editing = !!id;
  const navigate = useNavigate();
  const qc = useQueryClient();
  const existing = useQuery({ queryKey: ["job", id], queryFn: () => jobsApi.get(id!), enabled: editing });

  const { register, control, handleSubmit, reset, watch, setValue, formState: { errors } } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: DEFAULTS,
  });

  useEffect(() => {
    if (existing.data) {
      const j = existing.data;
      reset({ ...j, deadline: j.deadline ?? "", min_cgpa: j.min_cgpa != null ? String(j.min_cgpa) : "", application_form: j.application_form ?? [] });
    }
  }, [existing.data, reset]);

  const save = useMutation({
    mutationFn: (body: JobInput) => (editing ? jobsApi.update(id!, body) : jobsApi.create(body)),
    onSuccess: (job) => {
      toast.success(editing ? "Job updated" : "Job posted");
      qc.invalidateQueries({ queryKey: ["jobs"] });
      qc.invalidateQueries({ queryKey: ["job", job.id] });
      navigate(`/recruiter/jobs/${job.id}`);
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  if (editing && existing.isLoading) return <FullPageSpinner />;
  if (editing && existing.error) return <ErrorState message={errorMessage(existing.error)} />;

  const threshold = watch("screening_threshold");
  const numQ = watch("num_questions");
  const seconds = watch("seconds_per_question");
  const think = watch("think_seconds");
  const followUps = watch("follow_up_questions");
  const webcam = watch("require_webcam");
  const skills = watch("required_skills");
  const form = watch("application_form") ?? [];
  const description = watch("description") ?? "";
  const onSubmit = (v: Form) => save.mutate({ ...v, min_cgpa: v.min_cgpa.trim() ? Number(v.min_cgpa) : null, deadline: v.deadline ? v.deadline : null });

  return (
    <>
      <Link to={editing ? `/recruiter/jobs/${id}` : "/recruiter"} className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-900">
        ← {editing ? "Back to job" : "Jobs"}
      </Link>
      <PageHeader title={editing ? "Edit job" : "Post a new job"} subtitle="Set the minimum requirements first. Resumes below them are marked not qualified." />
      <form onSubmit={handleSubmit(onSubmit)} noValidate>
        <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
          <div className="min-w-0 space-y-6">
            <FormSection step={1} title="Role details" description="What candidates will see on the job page.">
              <Field label="Job title" htmlFor="title" error={errors.title?.message}>
                <TextInput id="title" invalid={!!errors.title} icon={<Briefcase />} placeholder="e.g. Junior Python Backend Developer" {...register("title")} />
              </Field>
              <Field label="Description" htmlFor="description" error={errors.description?.message} hint={`${description.trim().length} characters. Responsibilities, team and tech stack help the AI ask better questions.`}>
                <TextArea id="description" invalid={!!errors.description} rows={8} placeholder="Responsibilities, team, tech stack…" {...register("description")} />
              </Field>
              <Field label="Application deadline" htmlFor="deadline" optional hint="After this date the job stops accepting applications.">
                <TextInput id="deadline" type="date" icon={<CalendarDays />} {...register("deadline")} />
              </Field>
            </FormSection>

            <FormSection step={2} title="Minimum requirements" description="Hard rules. A candidate whose profile is below any of these sees why and cannot apply. The AI also checks the resume against them.">
              <div className="grid gap-5 sm:grid-cols-3">
                <Field label="Minimum degree" htmlFor="edu">
                  <Select id="edu" {...register("education_level")}>
                    {Object.entries(EDUCATION_LABEL).map(([v, l]) => <option key={v} value={v}>{v === "none" ? "No minimum" : `${l} or higher`}</option>)}
                  </Select>
                </Field>
                <Field label="Minimum experience" htmlFor="exp" error={errors.min_experience_years?.message}>
                  <TextInput id="exp" type="number" inputMode="numeric" min={0} max={40} suffix="years" invalid={!!errors.min_experience_years} {...register("min_experience_years")} />
                </Field>
                <Field label="Minimum CGPA" htmlFor="cgpa" optional error={errors.min_cgpa?.message} hint="Out of 4.0. Leave empty for no rule.">
                  <TextInput id="cgpa" type="number" inputMode="decimal" min={0} max={4} step={0.1} placeholder="e.g. 2.5" invalid={!!errors.min_cgpa} {...register("min_cgpa")} />
                </Field>
              </div>
            </FormSection>

            <FormSection step={3} title="Skills" description="The AI scores every resume against these skills, experience and education, out of 70.">
              <Field label="Required skills" htmlFor="skills" error={errors.required_skills?.message} hint="Press Enter after each skill. The AI matches them by meaning (e.g. “ReactJS” = “React”).">
                <Controller
                  name="required_skills"
                  control={control}
                  render={({ field }) => <TagInput id="skills" value={field.value} onChange={field.onChange} placeholder="Type a skill and press Enter" invalid={!!errors.required_skills} />}
                />
              </Field>
            </FormSection>

            <FormSection step={4} title="Extra questions" description="Optional. Degree, CGPA, experience and skills are already read from the resume. Set a must-have answer to stop candidates who don't meet it.">
              <Controller
                name="application_form"
                control={control}
                render={({ field }) => <FormBuilder value={field.value} onChange={field.onChange} />}
              />
              {errors.application_form && <p className="field-error">{errors.application_form.message ?? errors.application_form.root?.message}</p>}
            </FormSection>

            <FormSection step={5} title="Voice interview" description="Qualified candidates answer AI-generated questions by voice, in a locked full-screen window. Questions are read aloud and timed strictly.">
              <div>
                <p className="label" id="nq-label">Number of questions</p>
                <Controller
                  name="num_questions"
                  control={control}
                  render={({ field }) => (
                    <Segmented label="Number of questions" full value={Number(field.value)} onChange={field.onChange}
                      options={[5, 6, 7, 8].map((n) => ({ value: n, label: <>{n}<span className="hidden sm:inline"> questions</span></> }))} />
                  )}
                />
              </div>
              <Field label="Seconds per question" htmlFor="spq" error={errors.seconds_per_question?.message} hint={`About ${Math.round((Number(numQ) * Number(seconds)) / 60)} minutes in total.`}>
                <div className="flex flex-col gap-2 sm:flex-row">
                  <div className="sm:w-44"><TextInput id="spq" type="number" inputMode="numeric" min={30} max={600} step={10} suffix="sec" invalid={!!errors.seconds_per_question} {...register("seconds_per_question")} /></div>
                  <div className="flex flex-wrap gap-2">
                    {[60, 90, 120, 180].map((s) => (
                      <button key={s} type="button" onClick={() => setValue("seconds_per_question", s, { shouldValidate: true })}
                        className={clsx("h-10 rounded-lg px-4 text-sm font-semibold ring-1 transition", Number(seconds) === s ? "bg-brand-50 text-brand-700 ring-brand-300" : "bg-white text-slate-600 ring-slate-200 hover:ring-slate-300")}>
                        {s < 120 ? `${s}s` : `${s / 60} min`}
                      </button>
                    ))}
                  </div>
                </div>
              </Field>
              <Field label="Thinking time before recording starts" htmlFor="think" error={errors.think_seconds?.message} hint="After the question is read aloud, the candidate gets this many seconds to think. Then recording starts by itself.">
                <div className="flex flex-col gap-2 sm:flex-row">
                  <div className="sm:w-44"><TextInput id="think" type="number" inputMode="numeric" min={5} max={60} step={5} suffix="sec" invalid={!!errors.think_seconds} {...register("think_seconds")} /></div>
                  <div className="flex flex-wrap gap-2">
                    {[10, 15, 20, 30].map((s) => (
                      <button key={s} type="button" onClick={() => setValue("think_seconds", s, { shouldValidate: true })}
                        className={clsx("h-10 rounded-lg px-4 text-sm font-semibold ring-1 transition", Number(think) === s ? "bg-brand-50 text-brand-700 ring-brand-300" : "bg-white text-slate-600 ring-slate-200 hover:ring-slate-300")}>
                        {s}s
                      </button>
                    ))}
                  </div>
                </div>
              </Field>
              <div>
                <p className="label">Live follow-up questions</p>
                <Controller
                  name="follow_up_questions"
                  control={control}
                  render={({ field }) => (
                    <Segmented label="Live follow-up questions" full value={Number(field.value)} onChange={field.onChange}
                      options={[0, 1, 2, 3].map((n) => ({ value: n, label: n === 0 ? "None" : `${n}` }))} />
                  )}
                />
                <p className="mt-1.5 text-xs text-slate-500">The AI listens to an answer and asks a follow-up about what the candidate actually said. It can't be prepared in advance.</p>
              </div>
              <label className="flex items-start gap-3 rounded-xl border border-slate-200 p-4">
                <input type="checkbox" className="mt-0.5 h-4 w-4 accent-brand-600" {...register("require_webcam")} />
                <span>
                  <span className="block text-sm font-semibold text-slate-900">Require webcam (face and eye tracking)</span>
                  <span className="mt-0.5 block text-xs text-slate-500">
                    The candidate's camera stays on. The browser checks they are alone, facing the screen and looking at it, and
                    you get an attention score per answer plus a few photos. It flags for you to review and never rejects anyone on its own.
                  </span>
                </span>
              </label>
            </FormSection>
          </div>

          <aside className="space-y-6 lg:sticky lg:top-8 lg:self-start">
            <section className="card p-6">
              <div className="flex items-center justify-between">
                <label htmlFor="threshold" className="text-sm font-bold text-slate-900">Screening threshold</label>
                <span className="rounded-lg bg-brand-50 px-2.5 py-1 font-display text-lg font-bold tabular-nums text-brand-700">{threshold}<span className="text-xs font-semibold text-brand-400">/70</span></span>
              </div>
              <input id="threshold" type="range" min={0} max={70} step={1} className="range mt-5 w-full" style={{ ["--pct" as string]: `${(Number(threshold) / 70) * 100}%` }} {...register("screening_threshold")} />
              <div className="mt-1 flex justify-between text-[11px] font-medium text-slate-400"><span>Everyone</span><span>Strict</span></div>
              <p className="mt-4 rounded-xl bg-slate-50 p-3 text-xs leading-relaxed text-slate-600">
                Resume score = skills (40) + experience (20) + education (10). Candidates at or above <b>{threshold}</b> are invited to the
                voice interview automatically. Others are marked “not qualified” but stay visible to you. No rejection email is ever sent.
              </p>
            </section>
            <section className="card p-6">
              <p className="eyebrow">Summary</p>
              <dl className="mt-3 space-y-2.5 text-sm">
                <div className="flex justify-between gap-3"><dt className="text-slate-500">Minimum degree</dt><dd className="font-semibold">{watch("education_level") === "none" ? "None" : EDUCATION_LABEL[watch("education_level")]}</dd></div>
                <div className="flex justify-between gap-3"><dt className="text-slate-500">Minimum CGPA</dt><dd className="font-semibold">{watch("min_cgpa") ? Number(watch("min_cgpa")).toFixed(2) : "None"}</dd></div>
                <div className="flex justify-between gap-3"><dt className="text-slate-500">Skills</dt><dd className="font-semibold">{skills.length}</dd></div>
                <div className="flex justify-between gap-3"><dt className="text-slate-500">Extra questions</dt><dd className="font-semibold">{form.length} ({form.filter((q) => q.required).length} required)</dd></div>
                <div className="flex justify-between gap-3"><dt className="text-slate-500">Interview</dt><dd className="font-semibold">{numQ} × {seconds}s</dd></div>
                <div className="flex justify-between gap-3"><dt className="text-slate-500">Thinking time</dt><dd className="font-semibold">{think}s</dd></div>
                <div className="flex justify-between gap-3"><dt className="text-slate-500">Follow-ups</dt><dd className="font-semibold">{Number(followUps) || "None"}</dd></div>
                <div className="flex justify-between gap-3"><dt className="text-slate-500">Webcam</dt><dd className="font-semibold">{webcam ? "Required" : "Off"}</dd></div>
                <div className="flex justify-between gap-3"><dt className="text-slate-500">Auto-invite at</dt><dd className="font-semibold">{threshold}/70</dd></div>
              </dl>
              <div className="mt-6 flex gap-2">
                <Button type="button" variant="secondary" onClick={() => navigate(-1)}>Cancel</Button>
                <Button type="submit" className="flex-1" loading={save.isPending}>{editing ? "Save changes" : "Post job"}</Button>
              </div>
            </section>
          </aside>
        </div>
      </form>
    </>
  );
}
