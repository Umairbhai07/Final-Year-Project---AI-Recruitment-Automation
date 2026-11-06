import clsx from "clsx";
import { AlertCircle, CheckCircle2, Eye, EyeOff, Info } from "lucide-react";
import { forwardRef, useState, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { FieldError } from "./ui";

/** Label + control + hint/error, consistently spaced. */
export function Field({ label, htmlFor, hint, error, optional, children, className }: {
  label: string;
  htmlFor: string;
  hint?: ReactNode;
  error?: string;
  optional?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <label htmlFor={htmlFor} className="label flex items-center justify-between">
        <span>{label}</span>
        {optional && <span className="text-xs font-normal text-slate-400">Optional</span>}
      </label>
      {children}
      {error ? <FieldError message={error} /> : hint ? <p className="hint">{hint}</p> : null}
    </div>
  );
}

type InputProps = InputHTMLAttributes<HTMLInputElement> & { icon?: ReactNode; invalid?: boolean; suffix?: ReactNode };

/** Text input with an optional icon on the left and an optional suffix (e.g. a unit) on the right. */
export const TextInput = forwardRef<HTMLInputElement, InputProps>(function TextInput({ icon, invalid, suffix, className, ...props }, ref) {
  return (
    <div className="relative">
      {icon && <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 [&>svg]:h-[18px] [&>svg]:w-[18px]">{icon}</span>}
      <input ref={ref} aria-invalid={invalid || undefined} className={clsx("input", icon && "pl-10", suffix && "pr-16", className)} {...props} />
      {suffix && <span className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-xs font-medium text-slate-400">{suffix}</span>}
    </div>
  );
});

/** Password input with a show/hide toggle. */
export const PasswordInput = forwardRef<HTMLInputElement, InputProps>(function PasswordInput({ icon, invalid, className, ...props }, ref) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      {icon && <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 [&>svg]:h-[18px] [&>svg]:w-[18px]">{icon}</span>}
      <input ref={ref} type={show ? "text" : "password"} aria-invalid={invalid || undefined} className={clsx("input pr-11", icon && "pl-10", className)} {...props} />
      <button
        type="button"
        onClick={() => setShow((s) => !s)}
        className="absolute right-2 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700"
        aria-label={show ? "Hide password" : "Show password"}
      >
        {show ? <EyeOff className="h-[18px] w-[18px]" /> : <Eye className="h-[18px] w-[18px]" />}
      </button>
    </div>
  );
});

/** One box for a 6-digit code from an email. Digits only; phones show the number pad and can fill it in. */
export const CodeInput = forwardRef<HTMLInputElement, Omit<InputProps, "onChange" | "value"> & { value: string; onChange: (v: string) => void }>(
  function CodeInput({ value, onChange, className, invalid, ...props }, ref) {
    return (
      <input ref={ref} type="text" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]*" maxLength={6}
        aria-invalid={invalid || undefined} placeholder="000000" value={value}
        onChange={(e) => onChange(e.target.value.replace(/\D/g, "").slice(0, 6))}
        className={clsx("input text-center font-mono text-xl tracking-[0.5em]", className)} {...props} />
    );
  },
);

/** Phone number: only digits, spaces, dashes, brackets and a leading +, at most 20 characters. */
export function cleanPhone(v: string) {
  let out = v.replace(/[^\d+\-() ]/g, "").replace(/(?!^)\+/g, "");
  let digits = 0;
  out = [...out].filter((ch) => !/\d/.test(ch) || ++digits <= 16).join("");
  return out.slice(0, 20);
}

/** 0-4 score from simple rules, shown as a 4-segment bar. */
function passwordScore(pw: string) {
  let score = 0;
  if (pw.length >= 8) score++;
  if (/\d/.test(pw) && /[a-zA-Z]/.test(pw)) score++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
  if (pw.length >= 12 || /[^a-zA-Z0-9]/.test(pw)) score++;
  return score;
}

export function PasswordStrength({ password }: { password: string }) {
  if (!password) return null;
  const score = passwordScore(password);
  const labels = ["Too weak", "Weak", "Okay", "Good", "Strong"];
  const colors = ["bg-rose-500", "bg-rose-500", "bg-amber-500", "bg-emerald-500", "bg-emerald-600"];
  const rules = [
    { ok: password.length >= 8, text: "8+ characters" },
    { ok: /\d/.test(password), text: "a number" },
  ];
  return (
    <div className="mt-2" aria-live="polite">
      <div className="flex gap-1">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className={clsx("h-1.5 flex-1 rounded-full transition", i < score ? colors[score] : "bg-slate-200")} />
        ))}
      </div>
      <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2 text-xs">
        <span className="flex gap-3 text-slate-500">
          {rules.map((r) => (
            <span key={r.text} className={clsx("flex items-center gap-1", r.ok && "text-emerald-600")}>
              <CheckCircle2 className={clsx("h-3.5 w-3.5", !r.ok && "text-slate-300")} /> {r.text}
            </span>
          ))}
        </span>
        <span className="font-medium text-slate-600">{labels[score]}</span>
      </div>
    </div>
  );
}

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select({ className, ...props }, ref) {
  return <select ref={ref} className={clsx("select", className)} {...props} />;
});

export const TextArea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean }>(
  function TextArea({ className, invalid, ...props }, ref) {
    return <textarea ref={ref} aria-invalid={invalid || undefined} className={clsx("input", className)} {...props} />;
  },
);

/** Pill-style choice between a few options (e.g. Candidate / Recruiter, 5/6/7/8). */
export function Segmented<T extends string | number>({ value, onChange, options, label, size = "md", full }: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: ReactNode }[];
  label: string;
  size?: "sm" | "md";
  full?: boolean;
}) {
  return (
    <div role="tablist" aria-label={label} className={clsx("inline-flex rounded-xl bg-slate-100 p-1", full && "flex w-full")}>
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={String(o.value)}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(o.value)}
            className={clsx(
              "flex min-w-0 flex-1 items-center justify-center gap-2 whitespace-nowrap rounded-lg font-semibold transition",
              size === "sm" ? "h-7 px-3 text-xs" : "h-9 px-4 text-sm",
              active ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

export function Alert({ tone = "error", children }: { tone?: "error" | "info" | "success"; children: ReactNode }) {
  const styles = {
    error: "border-rose-200 bg-rose-50 text-rose-800",
    info: "border-brand-200 bg-brand-50 text-brand-800",
    success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  }[tone];
  const Icon = tone === "error" ? AlertCircle : tone === "success" ? CheckCircle2 : Info;
  return (
    <div role={tone === "error" ? "alert" : "status"} className={clsx("flex items-start gap-2.5 rounded-lg border px-3.5 py-3 text-sm", styles)}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div>{children}</div>
    </div>
  );
}

/** A titled block inside a long form, with a step number. */
export function FormSection({ step, title, description, children }: { step: number; title: string; description?: string; children: ReactNode }) {
  return (
    <section className="card p-6 sm:p-7">
      <div className="mb-6 flex items-start gap-3.5">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-600 text-xs font-bold text-white">{step}</span>
        <div>
          <h2 className="font-display text-base font-bold text-slate-900">{title}</h2>
          {description && <p className="mt-0.5 text-sm text-slate-500">{description}</p>}
        </div>
      </div>
      <div className="space-y-5">{children}</div>
    </section>
  );
}
