import { X } from "lucide-react";
import { useState, type KeyboardEvent } from "react";

/** Type a skill and press Enter or comma to add it as a chip. Backspace removes the last one. */
export function TagInput({ value, onChange, id, placeholder, invalid }: {
  value: string[];
  invalid?: boolean;
  onChange: (tags: string[]) => void;
  id?: string;
  placeholder?: string;
}) {
  const [draft, setDraft] = useState("");

  const add = (raw: string) => {
    const parts = raw.split(",").map((s) => s.trim()).filter(Boolean);
    const next = [...value];
    for (const p of parts) if (!next.some((t) => t.toLowerCase() === p.toLowerCase())) next.push(p.slice(0, 60));
    onChange(next);
    setDraft("");
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if ((e.key === "Enter" || e.key === ",") && draft.trim()) {
      e.preventDefault();
      add(draft);
    } else if (e.key === "Backspace" && !draft && value.length) {
      onChange(value.slice(0, -1));
    }
  };

  return (
    <div className={`flex min-h-[44px] flex-wrap items-center gap-1.5 rounded-xl border bg-white px-2 py-1.5 shadow-sm transition focus-within:border-brand-500 focus-within:ring-4 focus-within:ring-brand-100 ${invalid ? "border-rose-300" : "border-slate-200"}`}>
      {value.map((tag) => (
        <span key={tag} className="inline-flex items-center gap-1 rounded-lg bg-brand-50 px-2.5 py-1 text-xs font-semibold text-brand-700 ring-1 ring-brand-100">
          {tag}
          <button type="button" aria-label={`Remove ${tag}`} onClick={() => onChange(value.filter((t) => t !== tag))} className="rounded hover:text-brand-900">
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
      <input
        id={id}
        aria-invalid={invalid || undefined}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={onKeyDown}
        onBlur={() => draft.trim() && add(draft)}
        placeholder={value.length ? "" : placeholder}
        className="min-w-[120px] flex-1 border-0 bg-transparent px-1 py-1 text-sm focus:outline-none focus:ring-0"
      />
    </div>
  );
}
