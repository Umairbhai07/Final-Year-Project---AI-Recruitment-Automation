import clsx from "clsx";
import { useEffect, useRef, useState, type ReactNode } from "react";

export type MenuItem = { label: ReactNode; onClick: () => void; danger?: boolean; hidden?: boolean };

/** A button that opens a small list of actions. Closes on outside click or Escape. */
export function Menu({ trigger, items, label, align = "right", className }: {
  trigger: (open: boolean) => ReactNode;
  items: MenuItem[];
  label: string;
  align?: "left" | "right";
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);
  return (
    <div ref={ref} className={clsx("relative", className)}>
      <div onClick={() => setOpen((o) => !o)} aria-label={label} aria-expanded={open}>{trigger(open)}</div>
      {open && (
        <div role="menu" className={clsx("absolute z-30 mt-1 min-w-[11rem] overflow-hidden rounded-lg border border-slate-200 bg-white py-1 shadow-lg", align === "right" ? "right-0" : "left-0")}>
          {items.filter((i) => !i.hidden).map((i, n) => (
            <button key={n} type="button" role="menuitem" onClick={() => { setOpen(false); i.onClick(); }}
              className={clsx("block w-full whitespace-nowrap px-3 py-2 text-left text-sm hover:bg-slate-50", i.danger ? "text-rose-600" : "text-slate-700")}>
              {i.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
