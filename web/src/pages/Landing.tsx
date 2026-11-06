import clsx from "clsx";
import { ArrowRight, BarChart3, Check, Download, FileSearch, ListChecks, Lock, Mic, ShieldCheck, Smartphone, UserRound, X } from "lucide-react";
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Logo } from "../components/Layout";

/* The public home page: black and white, a few calm animations, no images (fast to load). */

const PREVIEW = [
  { name: "Ahmed Raza", role: "BS Computer Science · 3 yrs", score: 96 },
  { name: "Ayesha Noor", role: "BS Software Engineering · 1 yr", score: 79 },
  { name: "Usman Tariq", role: "BS Computer Science · 2 yrs", score: 74 },
  { name: "Sana Malik", role: "BBA · 4 yrs", score: 15 },
];

const STEPS = [
  { title: "Post a job", text: "Skills, minimum degree, experience and CGPA, and how the interview runs." },
  { title: "Candidates apply", text: "Only people whose profile meets your minimum requirements can apply." },
  { title: "AI screens and interviews", text: "Strong resumes get a spoken interview, scored answer by answer." },
  { title: "You decide", text: "One ranked list with charts, evidence and recordings." },
];

const MORE = [
  { icon: UserRound, title: "Candidate profiles", text: "Photo, education, experience and links, filled in once." },
  { icon: ListChecks, title: "Custom forms", text: "Ask notice period, salary or anything you need." },
  { icon: Lock, title: "One device per interview", text: "An interview can't be opened on a second computer." },
  { icon: Download, title: "Reports and export", text: "Printable reports, CSV and shortlist PDF." },
];

/** Adds `is-visible` to [data-reveal] elements as they scroll into view (once). */
function useReveal() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const items = ref.current?.querySelectorAll<HTMLElement>("[data-reveal]") ?? [];
    if (!("IntersectionObserver" in window)) {
      items.forEach((el) => el.classList.add("is-visible"));
      return;
    }
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add("is-visible");
          io.unobserve(e.target);
        }
      }),
      { rootMargin: "0px 0px -8% 0px", threshold: 0.12 },
    );
    items.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
  return ref;
}

const delay = (ms: number) => ({ transitionDelay: `${ms}ms` }) as CSSProperties;

function Nav() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return (
    <header className={clsx("fixed inset-x-0 top-0 z-40 border-b transition-colors duration-300", scrolled ? "border-neutral-200 bg-white/80 backdrop-blur-md" : "border-transparent bg-transparent")}>
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5 sm:px-8">
        <Logo mono />
        <nav className="hidden items-center gap-8 text-sm text-neutral-500 md:flex">
          <a href="#product" className="transition hover:text-neutral-950">Product</a>
          <a href="#how" className="transition hover:text-neutral-950">How it works</a>
          <a href="#teams" className="transition hover:text-neutral-950">For teams</a>
        </nav>
        <div className="flex items-center gap-2">
          <Link to="/login" className="hidden h-9 items-center px-3 text-sm font-medium text-neutral-600 transition hover:text-neutral-950 sm:inline-flex">Sign in</Link>
          <Link to="/register" className="inline-flex h-9 items-center rounded-md bg-neutral-950 px-4 text-sm font-medium text-white transition hover:bg-neutral-800">Get started</Link>
        </div>
      </div>
    </header>
  );
}

/** A still picture of the recruiter's job page, in black and white. */
function ProductPreview() {
  return (
    <div className="relative mx-auto max-w-4xl" aria-hidden>
      <div className="lp-glow absolute -inset-x-10 -top-10 bottom-0 -z-10" />
      <div className="overflow-hidden rounded-xl border border-neutral-200 bg-white text-left shadow-[0_30px_80px_-40px_rgba(0,0,0,.35)]">
        <div className="flex items-center gap-1.5 border-b border-neutral-100 bg-neutral-50/70 px-4 py-2.5">
          <span className="h-2.5 w-2.5 rounded-full bg-neutral-200" /><span className="h-2.5 w-2.5 rounded-full bg-neutral-200" /><span className="h-2.5 w-2.5 rounded-full bg-neutral-200" />
          <span className="ml-3 rounded bg-white px-2 py-0.5 text-[11px] text-neutral-400 ring-1 ring-neutral-200">recruitai.app/recruiter/jobs</span>
        </div>
        <div className="p-5 sm:p-7">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-xs text-neutral-400">Jobs</p>
              <p className="mt-1 text-lg font-semibold tracking-tight text-neutral-950">Junior Python Backend Developer</p>
              <p className="mt-0.5 text-xs text-neutral-500">Minimum: Bachelor's · CGPA 2.50+</p>
            </div>
            <div className="flex gap-6 text-right">
              {[["Applicants", "48"], ["Interviewed", "12"], ["Avg score", "78.4"]].map(([k, v]) => (
                <div key={k}><p className="text-xl font-semibold tabular-nums text-neutral-950">{v}</p><p className="text-[11px] text-neutral-400">{k}</p></div>
              ))}
            </div>
          </div>
          <div className="mt-5 divide-y divide-neutral-100 rounded-lg border border-neutral-200">
            {PREVIEW.map((p, i) => (
              <div key={p.name} className="grid grid-cols-[22px_1fr_110px] items-center gap-3 px-4 py-3 sm:grid-cols-[22px_1fr_180px]">
                <span className="text-xs tabular-nums text-neutral-400">{i + 1}</span>
                <div className="flex min-w-0 items-center gap-3">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-neutral-100 text-[10px] font-semibold text-neutral-600">{p.name.split(" ").map((x) => x[0]).join("")}</span>
                  <div className="min-w-0">
                    <p className="truncate text-[13px] font-medium text-neutral-900">{p.name}</p>
                    <p className="truncate text-[11px] text-neutral-400">{p.role}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2.5">
                  <span className="w-7 text-right text-[13px] font-semibold tabular-nums text-neutral-950">{p.score}</span>
                  <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-neutral-100">
                    <span className="lp-bar block h-full rounded-full bg-neutral-950" style={{ "--w": `${p.score}%`, transitionDelay: `${500 + i * 120}ms` } as CSSProperties} />
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="lp-float absolute -left-16 top-[58%] hidden rounded-lg border border-neutral-200 bg-white px-3.5 py-2.5 text-left shadow-lg lg:block">
        <p className="text-[11px] text-neutral-400">Resume match</p>
        <p className="mt-0.5 flex items-center gap-1.5 text-sm font-semibold text-neutral-950"><Check className="h-3.5 w-3.5" /> 5 of 5 skills</p>
      </div>
      <div className="lp-float absolute -right-14 bottom-10 hidden rounded-lg border border-neutral-200 bg-white px-3.5 py-2.5 text-left shadow-lg [animation-delay:-2s] lg:block">
        <p className="text-[11px] text-neutral-400">Interview</p>
        <p className="mt-0.5 text-sm font-semibold text-neutral-950">26.4 / 30</p>
      </div>
    </div>
  );
}

function Block({ className, icon: Icon, title, text, children, d = 0 }: { className?: string; icon: typeof Mic; title: string; text: string; children: ReactNode; d?: number }) {
  return (
    <div data-reveal style={delay(d)} className={clsx("lp-card group flex flex-col overflow-hidden rounded-2xl border border-neutral-200 bg-white", className)}>
      <div className="flex-1 border-b border-neutral-100 bg-neutral-50/60 p-6">{children}</div>
      <div className="p-6">
        <p className="flex items-center gap-2 text-sm font-semibold text-neutral-950"><Icon className="h-4 w-4" /> {title}</p>
        <p className="mt-1.5 text-sm leading-relaxed text-neutral-500">{text}</p>
      </div>
    </div>
  );
}

function ScreeningVisual() {
  const skills: [string, boolean][] = [["Python", true], ["FastAPI", true], ["SQL", true], ["Git", true], ["Docker", false]];
  return (
    <div className="grid h-full gap-4 sm:grid-cols-[1fr_150px]">
      <div className="rounded-lg border border-neutral-200 bg-white p-4">
        <div className="h-2 w-24 rounded bg-neutral-800" />
        <div className="mt-2 h-1.5 w-40 rounded bg-neutral-200" />
        <div className="mt-4 space-y-1.5">{[92, 80, 86, 60].map((w) => <div key={w} className="h-1.5 rounded bg-neutral-100" style={{ width: `${w}%` }} />)}</div>
        <div className="mt-4 flex flex-wrap gap-1.5">
          {skills.map(([s, ok]) => (
            <span key={s} className={clsx("inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium", ok ? "border-neutral-900 bg-neutral-950 text-white" : "border-dashed border-neutral-300 text-neutral-400")}>
              {ok ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />} {s}
            </span>
          ))}
        </div>
      </div>
      <div className="flex flex-col justify-center rounded-lg border border-neutral-200 bg-white p-4">
        <p className="text-[11px] text-neutral-400">Resume score</p>
        <p className="mt-1 text-3xl font-semibold tabular-nums tracking-tight text-neutral-950">62<span className="text-base text-neutral-400">/70</span></p>
        <div className="mt-3 space-y-1.5 text-[11px] text-neutral-500">
          <p className="flex justify-between"><span>Skills</span><span className="tabular-nums text-neutral-900">32/40</span></p>
          <p className="flex justify-between"><span>Experience</span><span className="tabular-nums text-neutral-900">20/20</span></p>
          <p className="flex justify-between"><span>Education</span><span className="tabular-nums text-neutral-900">10/10</span></p>
        </div>
      </div>
    </div>
  );
}

function VoiceVisual() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-5 py-4">
      <div className="flex h-14 items-center gap-[3px]">
        {Array.from({ length: 28 }, (_, i) => (
          <span key={i} className="lp-wave w-[3px] rounded-full bg-neutral-900" style={{ animationDelay: `${(i * 97) % 900}ms`, height: `${30 + ((i * 37) % 70)}%` }} />
        ))}
      </div>
      <p className="rounded-full border border-neutral-200 bg-white px-3 py-1 text-[11px] font-medium text-neutral-600">
        <span className="mr-1.5 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-neutral-950 align-middle" />Recording · 1:25 left
      </p>
    </div>
  );
}

function IntegrityVisual() {
  return (
    <div className="flex h-full items-center justify-center py-2">
      <div className="relative aspect-[4/3] w-full max-w-[240px] overflow-hidden rounded-lg border border-neutral-200 bg-white">
        <div className="absolute inset-0 bg-[radial-gradient(#e5e5e5_1px,transparent_1px)] [background-size:12px_12px]" />
        <div className="absolute left-1/2 top-[22%] h-12 w-12 -translate-x-1/2 rounded-full border-2 border-neutral-300" />
        <div className="absolute bottom-0 left-1/2 h-16 w-28 -translate-x-1/2 rounded-t-full border-2 border-b-0 border-neutral-300" />
        <div className="lp-scan absolute right-[14%] top-[34%] flex h-14 w-9 items-center justify-center rounded-md border-2 border-neutral-950">
          <Smartphone className="h-4 w-4 text-neutral-950" />
        </div>
        <span className="absolute left-2 top-2 rounded bg-neutral-950 px-1.5 py-0.5 text-[10px] font-medium text-white">Phone detected</span>
      </div>
    </div>
  );
}

function ChartsVisual() {
  const bars = [18, 30, 22, 46, 64, 52, 80, 58, 70, 40];
  return (
    <div className="grid h-full gap-4 sm:grid-cols-[1fr_170px]">
      <div className="flex h-full min-h-[130px] items-end gap-2 rounded-lg border border-neutral-200 bg-white p-4">
        {bars.map((h, i) => (
          <span key={i} className="lp-col flex-1 rounded-t bg-neutral-900" style={{ "--h": `${h}%`, transitionDelay: `${i * 60}ms`, opacity: 0.35 + (h / 80) * 0.65 } as CSSProperties} />
        ))}
      </div>
      <div className="space-y-2 rounded-lg border border-neutral-200 bg-white p-4 text-[11px] text-neutral-500">
        {[["Applied", 100], ["Screened", 62], ["Interviewed", 40], ["Shortlisted", 14]].map(([k, v]) => (
          <div key={k}>
            <p className="flex justify-between"><span>{k}</span><span className="tabular-nums text-neutral-900">{v}%</span></p>
            <span className="mt-1 block h-1 rounded-full bg-neutral-100"><span className="lp-bar block h-full rounded-full bg-neutral-950" style={{ "--w": `${v}%` } as CSSProperties} /></span>
          </div>
        ))}
      </div>
    </div>
  );
}

const Check2 = ({ children }: { children: ReactNode }) => (
  <li className="flex gap-3"><Check className="mt-0.5 h-4 w-4 shrink-0" /> <span>{children}</span></li>
);

export default function Landing() {
  const root = useReveal();
  return (
    <div ref={root} className="lp-root min-h-screen bg-white text-neutral-950 antialiased">
      <Nav />
      <main>
        {/* Hero */}
        <section className="relative overflow-hidden">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(#d4d4d4_1px,transparent_1px)] [background-size:24px_24px] [mask-image:radial-gradient(60%_50%_at_50%_0%,black,transparent)]" />
          <div className="relative mx-auto max-w-6xl px-5 pb-20 pt-32 text-center sm:px-8 sm:pt-40">
            <Link to="/register?role=recruiter" className="lp-in inline-flex items-center gap-2 rounded-full border border-neutral-200 bg-white px-3 py-1 text-xs font-medium text-neutral-600 shadow-sm transition hover:border-neutral-300">
              <span className="rounded-full bg-neutral-950 px-1.5 py-px text-[10px] font-semibold text-white">New</span>
              Phone detection in interviews <ArrowRight className="h-3 w-3" />
            </Link>
            <h1 className="lp-in mx-auto mt-6 max-w-4xl font-display text-[42px] font-bold leading-[1.04] tracking-[-0.04em] [animation-delay:80ms] sm:text-6xl lg:text-[76px]">
              Hire the right people.
              <br />
              <span className="text-neutral-400">In a fraction of the time.</span>
            </h1>
            <p className="lp-in mx-auto mt-6 max-w-xl text-base leading-relaxed text-neutral-500 [animation-delay:160ms] sm:text-lg">
              RecruitAI screens every resume against the role, runs a spoken interview in the browser and gives you one
              ranked shortlist, with the evidence behind every score.
            </p>
            <div className="lp-in mt-9 flex flex-col justify-center gap-3 [animation-delay:240ms] sm:flex-row">
              <Link to="/register?role=recruiter" className="group inline-flex h-11 items-center justify-center gap-2 rounded-md bg-neutral-950 px-6 text-sm font-medium text-white transition hover:bg-neutral-800">
                Start hiring <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
              </Link>
              <Link to="/register?role=candidate" className="inline-flex h-11 items-center justify-center rounded-md border border-neutral-200 bg-white px-6 text-sm font-medium text-neutral-900 transition hover:border-neutral-300 hover:bg-neutral-50">
                I'm looking for a job
              </Link>
            </div>
            <div data-reveal className="mt-16 sm:mt-20">
              <ProductPreview />
            </div>
          </div>
        </section>

        {/* Numbers */}
        <section className="border-y border-neutral-100">
          <div className="mx-auto grid max-w-6xl grid-cols-2 divide-neutral-100 px-5 sm:px-8 md:grid-cols-4 md:divide-x">
            {[["100", "point score, explained"], ["5 to 8", "spoken questions per role"], ["500", "users at once, tested"], ["0", "automatic rejections"]].map(([n, t], i) => (
              <div key={t} data-reveal style={delay(i * 80)} className="px-2 py-8 text-center md:px-6">
                <p className="text-3xl font-semibold tracking-tight">{n}</p>
                <p className="mt-1 text-sm text-neutral-500">{t}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Product */}
        <section id="product" className="scroll-mt-16">
          <div className="mx-auto max-w-6xl px-5 py-24 sm:px-8">
            <div data-reveal className="max-w-2xl">
              <p className="text-sm font-medium text-neutral-500">Product</p>
              <h2 className="mt-2 font-display text-3xl font-bold tracking-[-0.03em] sm:text-5xl">Everything from application to shortlist.</h2>
            </div>
            <div className="mt-12 grid gap-4 lg:grid-cols-3">
              <Block className="lg:col-span-2" icon={FileSearch} title="Resume screening" text="Every resume is scored for skills, experience and education against the role, with matched and missing skills listed.">
                <ScreeningVisual />
              </Block>
              <Block icon={Mic} title="Voice interviews" text="Questions are spoken, answers recorded and scored, with live follow ups." d={80}>
                <VoiceVisual />
              </Block>
              <Block icon={ShieldCheck} title="Interview integrity" text="Full screen, one device, and a camera that spots phones, notes and a second person." d={0}>
                <IntegrityVisual />
              </Block>
              <Block className="lg:col-span-2" icon={BarChart3} title="Rankings and charts" text="One list per job, plus the hiring funnel, score spread and missing skills at a glance." d={80}>
                <ChartsVisual />
              </Block>
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {MORE.map((m, i) => (
                <div key={m.title} data-reveal style={delay(i * 60)} className="lp-card rounded-2xl border border-neutral-200 p-5">
                  <m.icon className="h-4 w-4" />
                  <p className="mt-3 text-sm font-semibold">{m.title}</p>
                  <p className="mt-1 text-sm leading-relaxed text-neutral-500">{m.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* How it works */}
        <section id="how" className="scroll-mt-16 bg-neutral-50">
          <div className="mx-auto max-w-6xl px-5 py-24 sm:px-8">
            <div data-reveal className="max-w-2xl">
              <p className="text-sm font-medium text-neutral-500">How it works</p>
              <h2 className="mt-2 font-display text-3xl font-bold tracking-[-0.03em] sm:text-5xl">Four steps. No scheduling.</h2>
            </div>
            <ol className="relative mt-14 grid gap-8 sm:grid-cols-2 lg:grid-cols-4 lg:gap-6">
              <span className="lp-line absolute left-0 right-0 top-5 hidden h-px bg-neutral-200 lg:block" aria-hidden />
              {STEPS.map((s, i) => (
                <li key={s.title} data-reveal style={delay(i * 120)} className="relative">
                  <span className="relative flex h-10 w-10 items-center justify-center rounded-lg border border-neutral-200 bg-white text-sm font-semibold shadow-sm">{i + 1}</span>
                  <h3 className="mt-5 font-semibold">{s.title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-neutral-500">{s.text}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Audiences */}
        <section id="teams" className="mx-auto grid max-w-6xl scroll-mt-16 gap-4 px-5 py-24 sm:px-8 lg:grid-cols-2">
          <div data-reveal className="relative overflow-hidden rounded-2xl bg-neutral-950 p-8 text-white sm:p-10">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(rgba(255,255,255,.08)_1px,transparent_1px)] [background-size:20px_20px] [mask-image:linear-gradient(to_bottom_left,black,transparent_60%)]" />
            <p className="relative text-sm text-neutral-400">For recruiters</p>
            <h3 className="relative mt-2 font-display text-2xl font-bold tracking-tight sm:text-3xl">Spend your time on the shortlist, not the pile.</h3>
            <ul className="relative mt-6 space-y-3 text-sm text-neutral-300">
              <Check2>Screen hundreds of resumes in minutes</Check2>
              <Check2>Structured interviews without booking calls</Check2>
              <Check2>Scores with the evidence behind them</Check2>
            </ul>
            <Link to="/register?role=recruiter" className="group relative mt-8 inline-flex h-10 items-center gap-2 rounded-md bg-white px-5 text-sm font-medium text-neutral-950 transition hover:bg-neutral-200">
              Create a recruiter account <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
            </Link>
          </div>
          <div data-reveal style={delay(100)} className="rounded-2xl border border-neutral-200 p-8 sm:p-10">
            <p className="text-sm text-neutral-500">For candidates</p>
            <h3 className="mt-2 font-display text-2xl font-bold tracking-tight sm:text-3xl">Show what you can do, on your schedule.</h3>
            <ul className="mt-6 space-y-3 text-sm text-neutral-600">
              <Check2>See which jobs you qualify for before applying</Check2>
              <Check2>Interview from your browser, whenever it suits you</Check2>
              <Check2>Track every application in one place</Check2>
            </ul>
            <Link to="/register?role=candidate" className="group mt-8 inline-flex h-10 items-center gap-2 rounded-md bg-neutral-950 px-5 text-sm font-medium text-white transition hover:bg-neutral-800">
              Create a candidate account <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
            </Link>
          </div>
        </section>

        {/* CTA */}
        <section className="mx-auto max-w-6xl px-5 pb-24 sm:px-8">
          <div data-reveal className="relative overflow-hidden rounded-2xl border border-neutral-200 px-8 py-16 text-center sm:px-14">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(#e5e5e5_1px,transparent_1px)] [background-size:20px_20px] [mask-image:radial-gradient(50%_70%_at_50%_50%,black,transparent)]" />
            <h2 className="relative font-display text-3xl font-bold tracking-[-0.03em] sm:text-5xl">Ready to hire faster?</h2>
            <p className="relative mx-auto mt-4 max-w-md text-neutral-500">Create an account and post your first job in minutes.</p>
            <div className="relative mt-8 flex flex-col justify-center gap-3 sm:flex-row">
              <Link to="/register?role=recruiter" className="inline-flex h-11 items-center justify-center rounded-md bg-neutral-950 px-6 text-sm font-medium text-white transition hover:bg-neutral-800">Get started</Link>
              <Link to="/login" className="inline-flex h-11 items-center justify-center rounded-md border border-neutral-200 bg-white px-6 text-sm font-medium transition hover:bg-neutral-50">Sign in</Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-neutral-100">
        <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-4 px-5 py-8 text-sm text-neutral-500 sm:flex-row sm:items-center sm:px-8">
          <Logo mono size="sm" />
          <div className="flex gap-6">
            <Link to="/login" className="hover:text-neutral-950">Sign in</Link>
            <Link to="/register" className="hover:text-neutral-950">Create account</Link>
          </div>
          <p>© {new Date().getFullYear()} AI Recruitment Assistant</p>
        </div>
      </footer>
    </div>
  );
}
