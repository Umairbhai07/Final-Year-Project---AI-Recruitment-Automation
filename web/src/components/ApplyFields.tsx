import clsx from "clsx";
import type { FormQuestion } from "../api/types";
import type { Answers } from "../lib/answers";
import { Field, Select, TextArea, TextInput } from "./form";

/** The recruiter's application form, rendered for the candidate. */
export function ApplyFields({ questions, answers, errors, onChange }: {
  questions: FormQuestion[];
  answers: Answers;
  errors: Record<string, string>;
  onChange: (id: string, value: string) => void;
}) {
  return (
    <div className="space-y-4">
      {questions.map((q) => {
        const id = `q-${q.id}`;
        const value = answers[q.id] ?? "";
        const invalid = !!errors[q.id];
        const label = q.required ? `${q.label} *` : q.label;
        if (q.type === "yes_no") {
          return (
            <fieldset key={q.id}>
              <legend className="label flex w-full items-center justify-between">
                <span>{label}</span>
                {!q.required && <span className="text-xs font-normal text-slate-400">Optional</span>}
              </legend>
              <div role="radiogroup" aria-label={q.label} className="grid grid-cols-2 gap-2">
                {["Yes", "No"].map((opt) => (
                  <button key={opt} type="button" role="radio" aria-checked={value === opt} onClick={() => onChange(q.id, opt)}
                    className={clsx("h-11 rounded-xl text-sm font-semibold ring-1 transition",
                      value === opt ? "bg-brand-50 text-brand-700 ring-brand-400" : "bg-white text-slate-600 ring-slate-200 hover:ring-slate-300",
                      invalid && value !== opt && "ring-rose-300")}>
                    {opt}
                  </button>
                ))}
              </div>
              {errors[q.id] ? <p className="field-error">{errors[q.id]}</p> : q.help ? <p className="hint">{q.help}</p> : null}
            </fieldset>
          );
        }
        return (
          <Field key={q.id} label={label} htmlFor={id} optional={!q.required} error={errors[q.id]} hint={q.help ?? undefined}>
            {q.type === "select" ? (
              <Select id={id} value={value} aria-invalid={invalid || undefined} onChange={(e) => onChange(q.id, e.target.value)}>
                <option value="">Choose…</option>
                {q.options?.map((o) => <option key={o} value={o}>{o}</option>)}
              </Select>
            ) : q.type === "long_text" ? (
              <TextArea id={id} rows={3} value={value} invalid={invalid} maxLength={3000} onChange={(e) => onChange(q.id, e.target.value)} />
            ) : (
              <TextInput
                id={id}
                value={value}
                invalid={invalid}
                type={q.type === "number" ? "number" : q.type === "url" ? "url" : "text"}
                inputMode={q.type === "number" ? "decimal" : undefined}
                step={q.type === "number" ? "any" : undefined}
                min={q.min ?? undefined}
                max={q.max ?? undefined}
                maxLength={q.type === "number" ? undefined : 300}
                placeholder={q.type === "url" ? "https://" : undefined}
                onChange={(e) => onChange(q.id, e.target.value)}
              />
            )}
          </Field>
        );
      })}
    </div>
  );
}
