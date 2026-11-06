import clsx from "clsx";
import { AlertCircle, Loader2, X } from "lucide-react";
import { useEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { API_URL } from "../api/client";
import type { Tone } from "../lib/format";

type Variant = "primary" | "secondary" | "danger" | "ghost" | "success";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-brand-600 text-white shadow-sm hover:bg-brand-700",
  secondary: "bg-white text-slate-700 border border-slate-200 shadow-soft hover:border-slate-300 hover:bg-slate-50",
  danger: "bg-rose-600 text-white shadow-soft hover:bg-rose-700",
  success: "bg-emerald-600 text-white shadow-soft hover:bg-emerald-700",
  ghost: "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
};

export function Button({
  variant = "primary",
  size = "md",
  loading,
  className,
  children,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md" | "lg"; loading?: boolean }) {
  return (
    <button
      className={clsx(
        "inline-flex select-none items-center justify-center gap-2 whitespace-nowrap rounded-lg font-semibold transition duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none disabled:active:scale-100",
        size === "sm" && "h-8 px-3 text-xs",
        size === "md" && "h-10 px-4 text-sm",
        size === "lg" && "h-12 px-6 text-[15px]",
        VARIANTS[variant],
        className,
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={clsx("card", className)}>{children}</div>;
}

const TONES: Record<Tone, string> = {
  gray: "bg-slate-100 text-slate-700 ring-slate-200",
  blue: "bg-neutral-100 text-neutral-700 ring-neutral-200",
  green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  red: "bg-rose-50 text-rose-700 ring-rose-200",
  amber: "bg-amber-50 text-amber-800 ring-amber-200",
  violet: "bg-neutral-100 text-neutral-800 ring-neutral-300",
  brand: "bg-brand-50 text-brand-700 ring-brand-200",
};

export function Badge({ tone = "gray", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span className={clsx("inline-flex items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset", TONES[tone], className)}>
      {children}
    </span>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={clsx("animate-spin text-brand-600", className ?? "h-6 w-6")} aria-label="Loading" />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("skeleton", className)} aria-hidden />;
}

/** Placeholder shaped like a page (title, stat cards, a panel) while its data loads. */
export function FullPageSpinner() {
  return (
    <div className="animate-fade-in" role="status" aria-label="Loading">
      <Skeleton className="h-4 w-28" />
      <Skeleton className="mt-3 h-8 w-72 max-w-full" />
      <Skeleton className="mt-3 h-4 w-96 max-w-full" />
      <div className="mt-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
      </div>
      <Skeleton className="mt-6 h-64 rounded-xl" />
    </div>
  );
}

/** A few placeholder rows/cards for a list that is loading. */
export function ListSkeleton({ rows = 3, className }: { rows?: number; className?: string }) {
  return (
    <div className={clsx("space-y-3", className)} role="status" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
    </div>
  );
}

export function EmptyState({ icon, title, text, action }: { icon?: ReactNode; title: string; text?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center">
      {icon && <div className="mb-3 text-slate-300 [&>svg]:h-8 [&>svg]:w-8">{icon}</div>}
      <h3 className="font-display text-lg font-bold text-slate-900">{title}</h3>
      {text && <p className="mt-1 max-w-md text-sm text-slate-500">{text}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-center text-sm text-rose-800">
      <p>{message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" className="mt-3" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-bold leading-tight tracking-tight text-slate-900 sm:text-[26px]">{title}</h1>
        {subtitle && <div className="mt-1.5 text-sm text-slate-500">{subtitle}</div>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Modal({ open, onClose, title, children, footer }: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  // Focus the dialog once when it opens. (Depending on onClose here re-ran this on every keystroke in a form
  // inside the dialog, which moved focus away from the input and closed the phone keyboard.)
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && closeRef.current();
    document.addEventListener("keydown", onKey);
    if (!ref.current?.contains(document.activeElement)) ref.current?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);
  if (!open) return null;
  // Rendered into <body>, so a blurred or sticky header around the button can't clip or shift the dialog.
  return createPortal(
    <div className="fixed inset-0 z-50 flex overflow-y-auto bg-ink-950/50 p-3 backdrop-blur-sm sm:p-4" onMouseDown={onClose}>
      <div
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="m-auto w-full max-w-md animate-pop-in rounded-2xl bg-white shadow-2xl outline-none"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <h2 className="font-display text-base font-bold">{title}</h2>
          <button onClick={onClose} className="rounded p-1 text-slate-400 hover:bg-slate-100" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="px-5 py-4 text-sm text-slate-600">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-slate-100 px-5 py-3">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}

export function ConfirmDialog({ open, title, message, confirmLabel, danger, loading, onConfirm, onCancel }: {
  open: boolean;
  title: string;
  message: ReactNode;
  confirmLabel: string;
  danger?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={title}
      footer={
        <>
          <Button variant="secondary" onClick={onCancel}>Cancel</Button>
          <Button variant={danger ? "danger" : "primary"} loading={loading} onClick={onConfirm}>{confirmLabel}</Button>
        </>
      }
    >
      {message}
    </Modal>
  );
}

/** Horizontal bar showing value out of max. */
export function ScoreBar({ value, max, label, className }: { value: number | null; max: number; label?: string; className?: string }) {
  const pct = value === null ? 0 : Math.max(0, Math.min(100, (value / max) * 100));
  const color = pct >= 70 ? "bg-neutral-950" : pct >= 45 ? "bg-neutral-500" : "bg-neutral-300";
  return (
    <div className={clsx("w-full", className)}>
      {label && (
        <div className="mb-1 flex justify-between text-xs text-slate-600">
          <span>{label}</span>
          <span className="font-medium text-slate-800">{value === null ? "—" : `${Number(value.toFixed(1))} / ${max}`}</span>
        </div>
      )}
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100" role="meter" aria-valuenow={value ?? 0} aria-valuemin={0} aria-valuemax={max}>
        <div className={clsx("h-full rounded-full transition-all", value === null ? "" : color)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

/** Counts a number up from 0 when it first appears (keeps decimals; leaves text such as "—" alone). */
function CountUp({ value }: { value: ReactNode }) {
  const target = typeof value === "number" ? value : typeof value === "string" && /^-?\d+(\.\d+)?$/.test(value) ? Number(value) : null;
  const decimals = typeof value === "string" ? (value.split(".")[1]?.length ?? 0) : Number.isInteger(value) ? 0 : 1;
  const [shown, setShown] = useState(0);
  const from = useRef(0);
  useEffect(() => {
    if (target === null) return;
    const start = performance.now();
    const origin = from.current;
    from.current = target;
    let frame = 0;
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / 700);
      setShown(origin + (target - origin) * (1 - Math.pow(1 - t, 3)));
      if (t < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target]);
  if (target === null) return <>{value}</>;
  return <>{shown.toFixed(decimals)}</>;
}

const STAT_TONES: Record<string, string> = {
  brand: "bg-brand-50 text-brand-600",
  blue: "bg-neutral-100 text-neutral-700",
  green: "bg-emerald-50 text-emerald-600",
  amber: "bg-amber-50 text-amber-600",
  red: "bg-rose-50 text-rose-600",
  gray: "bg-slate-100 text-slate-600",
};
const STAT_ORDER = ["brand", "blue", "green", "amber", "red"];

/** A small number tile: label, value and an optional hint. */
export function StatCard({ label, value, hint, icon, tone, index = 0 }: {
  label: string;
  value: ReactNode;
  hint?: string;
  icon?: ReactNode;
  tone?: string;
  /** Position in a row of cards; picks a colour when no tone is given. */
  index?: number;
}) {
  const t = STAT_TONES[tone ?? STAT_ORDER[index % STAT_ORDER.length]] ?? STAT_TONES.brand;
  return (
    <Card className="p-4">
      <div className="flex items-center gap-3">
        {icon && <span className={clsx("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg [&>svg]:h-[18px] [&>svg]:w-[18px]", t)}>{icon}</span>}
        <div className="min-w-0">
          <div className="truncate text-xs font-medium text-slate-500">{label}</div>
          <div className="font-display text-2xl font-bold leading-tight tabular-nums text-slate-900"><CountUp value={value} /></div>
        </div>
      </div>
      {hint && <div className="mt-2 text-xs text-slate-500">{hint}</div>}
    </Card>
  );
}

/** A titled white panel. */
export function Panel({ title, subtitle, action, children, className, bodyClassName }: {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <Card className={clsx("flex flex-col", className)}>
      <div className="flex items-start justify-between gap-3 px-5 pb-1 pt-4">
        <div>
          <h2 className="text-[15px] font-semibold text-slate-900">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
        </div>
        {action}
      </div>
      <div className={clsx("flex-1 px-5 pb-5 pt-3", bodyClassName)}>{children}</div>
    </Card>
  );
}

/** Links the API returns as "/api/..." (photos) live on the API server, which may be another domain. */
export function fileUrl(path: string) {
  return path.startsWith("/api/") ? `${API_URL}${path}` : path;
}

function initialsOf(name: string) {
  return name.split(" ").filter(Boolean).map((p) => p[0]).slice(0, 2).join("").toUpperCase();
}

const AVATAR_BG = ["bg-neutral-900", "bg-neutral-700", "bg-neutral-500", "bg-neutral-800", "bg-neutral-600", "bg-neutral-400"];

/** A person's profile photo, or their initials when there is none (or it fails to load). */
export function Avatar({ name, src, size = 40, className }: { name: string; src?: string | null; size?: number; className?: string }) {
  const [broken, setBroken] = useState(false);
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  const style = { width: size, height: size, fontSize: Math.max(11, size * 0.36) };
  if (src && !broken) {
    return <img src={fileUrl(src)} alt="" style={style} onError={() => setBroken(true)} className={clsx("shrink-0 rounded-full object-cover ring-1 ring-black/5", className)} />;
  }
  return (
    <span style={style} className={clsx("flex shrink-0 items-center justify-center rounded-full font-semibold text-white", AVATAR_BG[h % AVATAR_BG.length], className)} aria-hidden>
      {initialsOf(name)}
    </span>
  );
}

/** Underlined tabs. */
export function Tabs<T extends string>({ value, onChange, tabs, className }: {
  value: T;
  onChange: (v: T) => void;
  tabs: { value: T; label: ReactNode; count?: number; highlight?: boolean }[];
  className?: string;
}) {
  return (
    <div className={clsx("flex gap-1 overflow-x-auto border-b border-slate-200", className)} role="tablist">
      {tabs.map((t) => (
        <button key={t.value} type="button" role="tab" aria-selected={value === t.value} onClick={() => onChange(t.value)}
          className={clsx("-mb-px flex shrink-0 items-center gap-1.5 border-b-2 px-3 py-2.5 text-sm transition-colors",
            value === t.value ? "border-brand-600 font-semibold text-slate-900" : "border-transparent text-slate-500 hover:text-slate-800")}>
          {t.label}
          {t.count !== undefined && (
            <span className={clsx("rounded-full px-1.5 text-[11px] font-semibold tabular-nums",
              t.highlight && t.count > 0 ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600")}>{t.count}</span>
          )}
        </button>
      ))}
    </div>
  );
}

/** Coloured score chip: green 70+, amber 45+, red below. */
export function ScoreChip({ value, className }: { value: number | null | undefined; className?: string }) {
  if (value === null || value === undefined) return <span className={clsx("text-sm text-slate-400", className)}>—</span>;
  const tone = value >= 70 ? "bg-emerald-50 text-emerald-700 ring-emerald-200" : value >= 45 ? "bg-amber-50 text-amber-700 ring-amber-200" : "bg-rose-50 text-rose-700 ring-rose-200";
  return <span className={clsx("inline-flex min-w-[2.5rem] justify-center rounded-md px-2 py-0.5 text-sm font-semibold tabular-nums ring-1 ring-inset", tone, className)}>{Number(value.toFixed(1)).toString()}</span>;
}

export function FieldError({ message }: { message?: string }) {
  return message ? <p className="field-error" role="alert"><AlertCircle className="h-3.5 w-3.5 shrink-0" />{message}</p> : null;
}
