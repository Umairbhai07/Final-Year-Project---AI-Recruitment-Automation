import clsx from "clsx";
import { Camera, CheckCircle2, FileText, Upload } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { Link, useSearchParams } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import { profileApi } from "../../api/endpoints";
import type { Profile, ProfileInput } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Alert, cleanPhone, Field, TextArea, TextInput } from "../../components/form";
import { Avatar, Button, ErrorState, FullPageSpinner, PageHeader, Panel } from "../../components/ui";

type Draft = { full_name: string; headline: string; phone: string; city: string; about: string };

function toDraft(p: Profile): Draft {
  const s = (v: string | null | undefined) => v ?? "";
  return { full_name: p.full_name, headline: s(p.headline), phone: s(p.phone), city: s(p.city), about: s(p.about) };
}

function toInput(d: Draft): ProfileInput {
  const t = (v: string) => (v.trim() ? v.trim() : null);
  return { full_name: d.full_name.trim(), headline: t(d.headline), phone: t(d.phone), city: t(d.city), about: t(d.about) };
}

function phoneError(v: string): string | null {
  const digits = v.replace(/\D/g, "").length;
  if (!v.trim()) return null;
  if (digits < 7) return "Enter a full phone number, for example +92 300 1234567";
  return null;
}

/** Shrink a photo to at most 480px on its longest side and save as JPEG, so uploads are small and fast. */
async function resizePhoto(file: File): Promise<Blob> {
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const i = new Image();
      i.onload = () => resolve(i);
      i.onerror = () => reject(new Error("That file is not an image we can read"));
      i.src = url;
    });
    const scale = Math.min(1, 480 / Math.max(img.width, img.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(img.width * scale);
    canvas.height = Math.round(img.height * scale);
    canvas.getContext("2d")!.drawImage(img, 0, 0, canvas.width, canvas.height);
    return await new Promise<Blob>((resolve, reject) =>
      canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("Could not read the photo"))), "image/jpeg", 0.88));
  } finally {
    URL.revokeObjectURL(url);
  }
}

export default function ProfilePage() {
  const qc = useQueryClient();
  const { refreshUser } = useAuth();
  const [params] = useSearchParams();
  const welcome = params.get("welcome") === "1";
  const profile = useQuery({ queryKey: ["profile", "me"], queryFn: profileApi.me });
  const [draft, setDraft] = useState<Draft | null>(null);
  const [dirty, setDirty] = useState(false);
  const photoInput = useRef<HTMLInputElement>(null);
  const resumeInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (profile.data && !dirty) setDraft(toDraft(profile.data));
  }, [profile.data, dirty]);

  const done = (p: Profile) => {
    qc.setQueryData(["profile", "me"], p);
    qc.invalidateQueries({ queryKey: ["jobs"] });
  };

  const save = useMutation({
    mutationFn: (d: Draft) => profileApi.save(toInput(d)),
    onSuccess: (p) => {
      setDirty(false);
      done(p);
      void refreshUser();
      toast.success(p.complete ? "Profile saved. You can apply to jobs now." : "Profile saved");
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const photo = useMutation({
    mutationFn: async (f: File) => profileApi.uploadPhoto(await resizePhoto(f)),
    onSuccess: (p) => { done(p); void refreshUser(); toast.success("Photo updated"); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const resume = useMutation({
    mutationFn: (f: File) => profileApi.uploadResume(f),
    onSuccess: (p) => { done(p); toast.success("Resume uploaded"); },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (profile.isLoading || (!draft && !profile.isError)) return <FullPageSpinner />;
  if (profile.isError || !profile.data || !draft) return <ErrorState message={errorMessage(profile.error)} onRetry={() => profile.refetch()} />;
  const p = profile.data;

  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => {
    setDraft((d) => (d ? { ...d, [key]: value } : d));
    setDirty(true);
  };

  const openResume = async () => {
    try {
      const r = await api.get("/profile/me/resume", { responseType: "blob" });
      window.open(URL.createObjectURL(r.data), "_blank", "noopener");
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  return (
    <div className="mx-auto max-w-5xl pb-24">
      <PageHeader
        title="My profile"
        subtitle="Recruiters see this profile when you apply. Fill it once and use it for every job."
      />

      {welcome && !p.complete && (
        <div className="mb-5">
          <Alert tone="info">Welcome! Complete your profile first. You can apply to jobs once every part below is filled in.</Alert>
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-[280px_1fr]">
        {/* Left: photo and progress */}
        <div className="space-y-5 lg:sticky lg:top-6 lg:self-start">
          <div className="card p-5 text-center">
            <div className="relative mx-auto w-fit">
              <Avatar name={p.full_name} src={p.photo_url} size={112} />
              <button type="button" onClick={() => photoInput.current?.click()} disabled={photo.isPending}
                className="absolute bottom-0 right-0 flex h-9 w-9 items-center justify-center rounded-full border-2 border-white bg-brand-600 text-white shadow hover:bg-brand-700"
                aria-label="Change photo">
                <Camera className="h-4 w-4" />
              </button>
            </div>
            <input ref={photoInput} type="file" accept="image/jpeg,image/png,image/webp" className="hidden"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) photo.mutate(f); e.target.value = ""; }} />
            <div className="mt-3 font-semibold text-slate-900">{p.full_name}</div>
            <div className="text-sm text-slate-500">{p.headline || p.email}</div>
            {photo.isPending && <div className="mt-2 text-xs text-slate-500">Uploading photo…</div>}
            {!p.photo_url && <p className="mt-2 text-xs text-slate-500">A clear photo of your face. JPG or PNG.</p>}
          </div>

          <div className="card p-5">
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-semibold text-slate-900">Profile complete</span>
              <span className="text-lg font-bold tabular-nums text-slate-900">{p.completion}%</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
              <div className={clsx("h-full rounded-full transition-all", p.complete ? "bg-neutral-950" : "bg-neutral-500")} style={{ width: `${p.completion}%` }} />
            </div>
            {p.complete ? (
              <p className="mt-3 flex items-center gap-1.5 text-sm text-emerald-700"><CheckCircle2 className="h-4 w-4" /> Ready to apply</p>
            ) : (
              <>
                <p className="mt-3 text-xs font-medium text-slate-500">Still needed</p>
                <ul className="mt-1.5 space-y-1">
                  {p.missing.map((m) => (
                    <li key={m} className="flex items-center gap-2 text-sm text-slate-700"><span className="h-1.5 w-1.5 rounded-full bg-amber-500" />{m}</li>
                  ))}
                </ul>
              </>
            )}
            {p.complete && <Link to="/jobs" className="mt-3 inline-block text-sm font-semibold text-brand-700 hover:underline">Find jobs</Link>}
          </div>
        </div>

        {/* Right: the form */}
        <form className="space-y-5" onSubmit={(e) => {
          e.preventDefault();
          if (draft.full_name.trim().length < 2) return void toast.error("Enter your full name");
          if (phoneError(draft.phone)) return void toast.error(phoneError(draft.phone)!);
          save.mutate(draft);
        }}>
          <Panel title="About you">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Full name" htmlFor="full_name">
                <TextInput id="full_name" autoComplete="name" maxLength={120} value={draft.full_name} onChange={(e) => set("full_name", e.target.value)} />
              </Field>
              <Field label="Headline" htmlFor="headline" optional hint="e.g. Junior Python developer">
                <TextInput id="headline" value={draft.headline} onChange={(e) => set("headline", e.target.value)} maxLength={120} />
              </Field>
              <Field label="Phone" htmlFor="phone" error={phoneError(draft.phone) ?? undefined}>
                <TextInput id="phone" type="tel" inputMode="tel" autoComplete="tel" maxLength={20} value={draft.phone}
                  onChange={(e) => set("phone", cleanPhone(e.target.value))} placeholder="+92 300 1234567" invalid={!!phoneError(draft.phone)} />
              </Field>
              <Field label="City" htmlFor="city">
                <TextInput id="city" autoComplete="address-level2" maxLength={80} value={draft.city} onChange={(e) => set("city", e.target.value)} placeholder="Lahore" />
              </Field>
              <Field label="Short summary" htmlFor="about" optional className="sm:col-span-2">
                <TextArea id="about" rows={3} value={draft.about} onChange={(e) => set("about", e.target.value)} maxLength={2000}
                  placeholder="Two or three lines about what you do and what you are looking for." />
              </Field>
            </div>
          </Panel>

          <Panel title="Resume" subtitle="Your degree, experience, skills and CGPA are read from it. You can still upload a different one for a single job.">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex min-w-0 flex-1 items-center gap-3 rounded-lg border border-slate-200 px-3 py-2.5">
                <FileText className="h-5 w-5 shrink-0 text-slate-400" />
                {p.has_resume ? (
                  <button type="button" onClick={openResume} className="truncate text-sm font-medium text-brand-700 hover:underline">{p.resume_filename}</button>
                ) : (
                  <span className="text-sm text-slate-500">No resume yet. PDF, up to 5 MB.</span>
                )}
              </div>
              <Button type="button" variant="secondary" loading={resume.isPending} onClick={() => resumeInput.current?.click()}>
                <Upload className="h-4 w-4" /> {p.has_resume ? "Replace" : "Upload PDF"}
              </Button>
              <input ref={resumeInput} type="file" accept="application/pdf" className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) resume.mutate(f); e.target.value = ""; }} />
            </div>
          </Panel>

          {dirty && (
            <div className="sticky bottom-4 z-10 flex animate-fade-in items-center justify-end gap-3 rounded-xl border border-slate-200 bg-white/95 px-4 py-3 shadow-lg backdrop-blur">
              <span className="mr-auto text-sm text-slate-600">You have unsaved changes</span>
              <Button type="button" variant="ghost" onClick={() => { setDirty(false); setDraft(toDraft(p)); }}>Undo</Button>
              <Button type="submit" loading={save.isPending}>Save profile</Button>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
