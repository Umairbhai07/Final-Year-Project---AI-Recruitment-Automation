import clsx from "clsx";
import { ArrowDown, ArrowUp, Plus, Trash2, X } from "lucide-react";
import { useState } from "react";
import type { FormQuestion, QuestionType } from "../api/types";
import { PRESET_QUESTIONS, TYPE_LABEL } from "../lib/formPresets";
import { Select, TextInput } from "./form";
import { Badge, Button } from "./ui";

const MAX = 15;

function slug(label: string, taken: string[]) {
  const base = label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 30) || "question";
  let id = base;
  for (let i = 2; taken.includes(id); i++) id = `${base}_${i}`;
  return id;
}

/** On/off switch used for "Required". */
function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button type="button" role="switch" aria-checked={checked} aria-label={label} onClick={() => onChange(!checked)}
      className="flex items-center gap-2 text-xs font-semibold text-slate-600">
      <span className={clsx("relative h-5 w-9 rounded-full transition", checked ? "bg-brand-600" : "bg-slate-300")}>
        <span className={clsx("absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all", checked ? "left-[18px]" : "left-0.5")} />
      </span>
      Required
    </button>
  );
}

const numOrNull = (v: string) => (v.trim() === "" || Number.isNaN(Number(v)) ? null : Number(v));

/** Must-have rule: an answer outside it marks the application "not qualified" at once, and the candidate is told
 * why. Candidates never see the passing answer. */
function MustRule({ q, onChange }: { q: FormQuestion; onChange: (patch: Partial<FormQuestion>) => void }) {
  const choices = q.type === "yes_no" ? ["Yes", "No"] : q.type === "select" ? q.options ?? [] : null;
  if (choices) {
    return (
      <label className="mt-2 flex flex-wrap items-center gap-2 px-1.5 text-xs text-slate-600">
        Must-have answer
        <select className="select h-8 w-auto py-0 text-xs" value={q.accept?.[0] ?? ""}
          onChange={(e) => onChange(e.target.value ? { accept: [e.target.value], required: true } : { accept: [] })}>
          <option value="">Any answer</option>
          {choices.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </label>
    );
  }
  if (q.type !== "number") return null;
  const set = (key: "must_min" | "must_max", v: string) => {
    const n = numOrNull(v);
    const other = key === "must_min" ? q.must_max : q.must_min;
    onChange({ [key]: n, ...(n !== null || other != null ? { required: true } : {}) });
  };
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 px-1.5 text-xs text-slate-600">
      Must be at least
      <input type="number" inputMode="decimal" className="input h-8 w-24 px-2 text-xs" placeholder="any" aria-label={`${q.label}: lowest passing answer`}
        value={q.must_min ?? ""} onChange={(e) => set("must_min", e.target.value)} />
      and at most
      <input type="number" inputMode="decimal" className="input h-8 w-28 px-2 text-xs" placeholder="any" aria-label={`${q.label}: highest passing answer`}
        value={q.must_max ?? ""} onChange={(e) => set("must_max", e.target.value)} />
    </div>
  );
}

function CustomEditor({ taken, onAdd, onCancel }: { taken: string[]; onAdd: (q: FormQuestion) => void; onCancel: () => void }) {
  const [label, setLabel] = useState("");
  const [type, setType] = useState<QuestionType>("text");
  const [options, setOptions] = useState("");
  const [required, setRequired] = useState(false);
  const [error, setError] = useState("");
  const add = () => {
    const opts = options.split(",").map((o) => o.trim()).filter(Boolean);
    if (label.trim().length < 2) return setError("Write the question first.");
    if (type === "select" && opts.length < 2) return setError("Add at least two options, separated by commas.");
    onAdd({ id: slug(label, taken), label: label.trim(), type, required, options: type === "select" ? opts : [] });
  };
  return (
    <div className="rounded-xl border border-brand-200 bg-brand-50/40 p-4">
      <div className="grid gap-3 sm:grid-cols-[1fr_180px]">
        <div>
          <label htmlFor="cq-label" className="label">Your question</label>
          <TextInput id="cq-label" autoFocus value={label} onChange={(e) => { setLabel(e.target.value); setError(""); }}
            placeholder="e.g. Which Python frameworks have you used?" maxLength={200} />
        </div>
        <div>
          <label htmlFor="cq-type" className="label">Answer type</label>
          <Select id="cq-type" value={type} onChange={(e) => setType(e.target.value as QuestionType)}>
            {Object.entries(TYPE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </Select>
        </div>
      </div>
      {type === "select" && (
        <div className="mt-3">
          <label htmlFor="cq-options" className="label">Options (comma separated)</label>
          <TextInput id="cq-options" value={options} onChange={(e) => setOptions(e.target.value)} placeholder="Lahore, Karachi, Islamabad" />
        </div>
      )}
      {error && <p className="field-error">{error}</p>}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <Toggle checked={required} onChange={setRequired} label="Required" />
        <div className="flex gap-2">
          <Button type="button" size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
          <Button type="button" size="sm" onClick={add}><Plus className="h-4 w-4" /> Add question</Button>
        </div>
      </div>
    </div>
  );
}

/** Recruiter picks which questions candidates answer when applying, which are compulsory, and which answers are
 * a must (e.g. "Can you work on-site?" must be Yes). */
export function FormBuilder({ value, onChange }: { value: FormQuestion[]; onChange: (v: FormQuestion[]) => void }) {
  const [custom, setCustom] = useState(false);
  const ids = value.map((q) => q.id);
  const presets = PRESET_QUESTIONS.filter((p) => !ids.includes(p.id));
  const update = (i: number, patch: Partial<FormQuestion>) => onChange(value.map((q, j) => (j === i ? { ...q, ...patch } : q)));
  const move = (i: number, d: number) => {
    const next = [...value];
    [next[i], next[i + d]] = [next[i + d], next[i]];
    onChange(next);
  };
  const full = value.length >= MAX;

  return (
    <div className="space-y-4">
      {value.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500">
          No questions. Candidates will only upload a resume.
        </p>
      ) : (
        <ol className="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200" aria-label="Form questions">
          {value.map((q, i) => (
            <li key={q.id} className="flex flex-col gap-3 bg-white px-4 py-3 sm:flex-row sm:items-center">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-slate-100 text-xs font-bold text-slate-500">{i + 1}</span>
              <div className="min-w-0 flex-1">
                <input aria-label={`Question ${i + 1} text`} value={q.label} maxLength={200}
                  onChange={(e) => update(i, { label: e.target.value })}
                  className="w-full rounded-lg border border-transparent bg-transparent px-1.5 py-1 text-sm font-semibold text-slate-900 hover:border-slate-200 focus:border-brand-400 focus:outline-none" />
                <div className="mt-0.5 flex flex-wrap items-center gap-1.5 px-1.5">
                  <Badge>{TYPE_LABEL[q.type]}</Badge>
                  {q.type === "select" && <span className="truncate text-xs text-slate-400">{q.options?.join(" · ")}</span>}
                </div>
                <MustRule q={q} onChange={(patch) => update(i, patch)} />
              </div>
              <div className="flex items-center gap-1">
                <Toggle checked={q.required} onChange={(v) => update(i, { required: v })} label={`Required: ${q.label}`} />
                <span className="mx-1 h-5 w-px bg-slate-200" />
                <button type="button" onClick={() => move(i, -1)} disabled={i === 0} aria-label={`Move ${q.label} up`}
                  className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 disabled:opacity-30"><ArrowUp className="h-4 w-4" /></button>
                <button type="button" onClick={() => move(i, 1)} disabled={i === value.length - 1} aria-label={`Move ${q.label} down`}
                  className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 disabled:opacity-30"><ArrowDown className="h-4 w-4" /></button>
                <button type="button" onClick={() => onChange(value.filter((_, j) => j !== i))} aria-label={`Remove ${q.label}`}
                  className="rounded-lg p-1.5 text-slate-400 hover:bg-rose-50 hover:text-rose-600"><Trash2 className="h-4 w-4" /></button>
              </div>
            </li>
          ))}
        </ol>
      )}

      {custom ? (
        <CustomEditor taken={ids} onCancel={() => setCustom(false)} onAdd={(q) => { onChange([...value, q]); setCustom(false); }} />
      ) : (
        <div>
          <p className="label">Add a question</p>
          <div className="flex flex-wrap gap-2">
            {presets.map((p) => (
              <button key={p.id} type="button" disabled={full} onClick={() => onChange([...value, { ...p }])}
                className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 transition hover:bg-brand-50 hover:text-brand-700 hover:ring-brand-200 disabled:opacity-40">
                <Plus className="h-3.5 w-3.5" /> {p.label}
              </button>
            ))}
            <button type="button" disabled={full} onClick={() => setCustom(true)}
              className="inline-flex items-center gap-1.5 rounded-full bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white shadow-soft hover:bg-brand-700 disabled:opacity-40">
              <Plus className="h-3.5 w-3.5" /> Write your own question
            </button>
          </div>
          {full && <p className="hint flex items-center gap-1"><X className="h-3.5 w-3.5" /> Maximum {MAX} questions.</p>}
        </div>
      )}
    </div>
  );
}
