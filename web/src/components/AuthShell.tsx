import { ArrowLeft, Check } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { Role } from "../api/types";
import { Logo } from "./Layout";

/** Sign-in pages: the form on white, and a black panel beside it on large screens. Square corners throughout. */
export function AuthShell({ children }: { role?: Role; children: ReactNode }) {
  return (
    <div className="auth-mono grid min-h-screen bg-white text-neutral-950 antialiased lg:grid-cols-[1fr_minmax(420px,44%)]">
      <div className="flex min-h-screen flex-col">
        <header className="flex h-16 shrink-0 items-center justify-between px-5 sm:px-8">
          <Logo mono />
          <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-neutral-500 transition hover:text-neutral-950">
            <ArrowLeft className="h-4 w-4" /> Home
          </Link>
        </header>
        <main className="flex flex-1 items-center justify-center px-5 pb-10 sm:px-8">
          <div className="lp-in w-full max-w-[400px]">{children}</div>
        </main>
      </div>

      <aside className="relative hidden overflow-hidden bg-neutral-950 text-white lg:flex lg:flex-col lg:justify-between lg:p-12" aria-hidden>
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(rgba(255,255,255,.09)_1px,transparent_1px)] [background-size:22px_22px] [mask-image:radial-gradient(70%_60%_at_70%_30%,black,transparent)]" />
        <p className="relative text-sm text-neutral-400">AI Recruitment Assistant</p>
        <div className="relative">
          <h2 className="max-w-md font-display text-4xl font-bold leading-tight tracking-[-0.03em]">Fair, fast first rounds for every role.</h2>
          <ul className="mt-8 space-y-3 text-sm text-neutral-300">
            {["Resumes screened against the role", "Spoken interviews, scored answer by answer", "One ranked shortlist with the evidence"].map((t) => (
              <li key={t} className="flex gap-3"><Check className="mt-0.5 h-4 w-4 shrink-0 text-white" /> {t}</li>
            ))}
          </ul>
          <div className="lp-float mt-12 max-w-sm border border-white/15 bg-white/[.04] p-5 backdrop-blur">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">Ahmed Raza</p>
                <p className="text-xs text-neutral-400">Junior Python Backend Developer</p>
              </div>
              <p className="text-2xl font-semibold tabular-nums">96.4</p>
            </div>
            <div className="mt-4 space-y-2 text-xs text-neutral-400">
              {[["Resume", 100], ["Interview", 88]].map(([k, v]) => (
                <div key={k} className="flex items-center gap-3">
                  <span className="w-16">{k}</span>
                  <span className="h-1 flex-1 bg-white/10"><span className="block h-full bg-white" style={{ width: `${v}%` }} /></span>
                </div>
              ))}
            </div>
          </div>
        </div>
        <p className="relative text-xs text-neutral-500">Every final decision stays with the recruiter.</p>
      </aside>
    </div>
  );
}
