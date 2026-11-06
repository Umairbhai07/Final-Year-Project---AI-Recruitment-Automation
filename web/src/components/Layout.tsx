import clsx from "clsx";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, FileText, KeyRound, LayoutDashboard, LogOut, Menu, PlusCircle, Search, UserRound, X, type LucideIcon } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { profileApi } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { VerifyBanner } from "./VerifyBanner";
import { prefetchProps } from "../lib/prefetch";
import { ChangePasswordModal } from "./ChangePassword";
import { Avatar } from "./ui";

/** The brand mark: a candidate with an AI spark, on the brand gradient. */
export function LogoMark({ className = "h-9 w-9", mono = true }: { className?: string; mono?: boolean }) {
  // Each copy needs its own gradient id: a hidden copy (the closed mobile menu) would otherwise blank the others.
  const gid = `ara-g-${useId().replace(/:/g, "")}`;
  return (
    <svg viewBox="0 0 40 40" className={clsx("shrink-0", className)} aria-hidden>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#6366f1" />
          <stop offset=".6" stopColor="#7c3aed" />
          <stop offset="1" stopColor="#c026d3" />
        </linearGradient>
      </defs>
      <rect width="40" height="40" rx={mono ? 9 : 11} fill={mono ? "#0a0a0a" : `url(#${gid})`} />
      <circle cx="18" cy="15" r="5.2" fill="#fff" />
      <path d="M8.5 31c1.2-5.6 5-8.6 9.5-8.6s8.3 3 9.5 8.6" fill="none" stroke="#fff" strokeWidth="3.4" strokeLinecap="round" />
      <path d="M30 6.5l1.3 3.2 3.2 1.3-3.2 1.3L30 15.5l-1.3-3.2-3.2-1.3 3.2-1.3z" fill={mono ? "#fff" : "#fde68a"} />
    </svg>
  );
}

/** Icon plus a short name. */
/** `mono`: black and white, for the public pages. */
export function Logo({ light, mono = true, size = "md", to = "/" }: { light?: boolean; mono?: boolean; size?: "sm" | "md" | "lg"; to?: string }) {
  return (
    <Link to={to} aria-label="AI Recruitment Assistant, home" className="flex items-center gap-2.5">
      <LogoMark mono={mono} className={size === "lg" ? "h-10 w-10" : size === "md" ? "h-9 w-9" : "h-8 w-8"} />
      <span className={clsx("font-display font-extrabold leading-none tracking-tight", size === "lg" ? "text-[22px]" : size === "md" ? "text-xl" : "text-lg", light ? "text-white" : "text-slate-900")}>
        Recruit<span className={mono ? (light ? "text-white/60" : "text-neutral-400") : light ? "text-fuchsia-300" : "text-gradient"}>AI</span>
      </span>
    </Link>
  );
}

function useLogout() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  return async () => {
    await logout();
    navigate("/login");
  };
}

/* ---------------------------------------------------------------- Portals: one shell for both roles */

type NavItem = { to: string; label: string; icon: LucideIcon; end?: boolean };

const RECRUITER_LINKS: NavItem[] = [
  { to: "/recruiter", label: "Jobs", icon: LayoutDashboard, end: true },
  { to: "/recruiter/jobs/new", label: "Post a job", icon: PlusCircle, end: true },
];

const CANDIDATE_LINKS: NavItem[] = [
  { to: "/jobs", label: "Find jobs", icon: Search, end: true },
  { to: "/applications", label: "My applications", icon: FileText },
  { to: "/profile", label: "My profile", icon: UserRound },
];

function SideNav({ links, onNavigate }: { links: NavItem[]; onNavigate?: () => void }) {
  const qc = useQueryClient();
  const { pathname } = useLocation();
  const { user } = useAuth();
  const profile = useQuery({ queryKey: ["profile", "me"], queryFn: profileApi.me, enabled: user?.role === "candidate", staleTime: 60_000 });
  return (
    <nav className="space-y-0.5 px-3" aria-label="Main">
      {links.map(({ to, label, icon: Icon, end }) => {
        // "Jobs" also covers a job's pages, but not "Post a job"
        const jobPages = to === "/recruiter" && pathname.startsWith("/recruiter/") && pathname !== "/recruiter/jobs/new";
        const incomplete = to === "/profile" && profile.data && !profile.data.complete;
        return (
          <NavLink key={to} to={to} end={end} onClick={onNavigate} {...prefetchProps(qc, to)}
            className={({ isActive }) => clsx(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              isActive || jobPages ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
            )}>
            <Icon className="h-[18px] w-[18px]" />
            <span className="flex-1">{label}</span>
            {incomplete && <span className="rounded-full bg-amber-100 px-1.5 text-[11px] font-semibold text-amber-800">{profile.data!.completion}%</span>}
          </NavLink>
        );
      })}
    </nav>
  );
}

function SidebarContent({ role, onNavigate }: { role: "recruiter" | "candidate"; onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col border-r border-slate-200 bg-white">
      <div className={clsx("flex h-16 items-center px-5", onNavigate && "pr-12")}>
        <Logo size="sm" to={role === "recruiter" ? "/recruiter" : "/jobs"} />
      </div>
      <p className="px-6 pb-2 pt-4 text-[11px] font-semibold uppercase tracking-wider text-slate-400">{role === "recruiter" ? "Recruiter" : "Candidate"}</p>
      <SideNav links={role === "recruiter" ? RECRUITER_LINKS : CANDIDATE_LINKS} onNavigate={onNavigate} />
    </div>
  );
}

function UserMenu() {
  const { user } = useAuth();
  const logout = useLogout();
  const [open, setOpen] = useState(false);
  const [pwOpen, setPwOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  if (!user) return null;
  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2.5 rounded-lg py-1.5 pl-1.5 pr-2 transition hover:bg-slate-100"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Account menu for ${user.full_name}`}
      >
        <Avatar key={user.photo_url ?? "none"} name={user.full_name} src={user.photo_url} size={32} className="bg-neutral-950" />
        <span className="hidden text-left md:block">
          <span className="block text-sm font-semibold leading-tight text-slate-900">{user.full_name}</span>
          <span className="block text-xs capitalize leading-tight text-slate-500">{user.role}</span>
        </span>
        <ChevronDown className={clsx("h-4 w-4 text-slate-400 transition", open && "rotate-180")} />
      </button>
      {open && (
        <div role="menu" className="absolute right-0 z-40 mt-2 w-60 origin-top-right animate-pop-in overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg">
          <div className="border-b border-slate-100 px-4 py-3">
            <p className="text-sm font-medium text-slate-900">{user.full_name}</p>
            <p className="truncate text-xs text-slate-500">{user.email}</p>
          </div>
          <button role="menuitem" onClick={() => { setOpen(false); setPwOpen(true); }} className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50">
            <KeyRound className="h-4 w-4 text-slate-400" /> Change password
          </button>
          <button role="menuitem" onClick={logout} className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50">
            <LogOut className="h-4 w-4 text-slate-400" /> Log out
          </button>
        </div>
      )}
      <ChangePasswordModal open={pwOpen} onClose={() => setPwOpen(false)} />
    </div>
  );
}

function PortalLayout({ role }: { role: "recruiter" | "candidate" }) {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => setOpen(false), [pathname]);
  return (
    <div className="dot-canvas min-h-screen">
      <aside className="no-print fixed inset-y-0 left-0 z-40 hidden w-60 lg:block">
        <SidebarContent role={role} />
      </aside>
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 animate-fade-in bg-slate-900/30" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 max-w-[85vw] animate-slide-in-left overflow-y-auto shadow-xl">
            <button onClick={() => setOpen(false)} className="absolute right-3 top-4 z-10 rounded-lg p-1.5 text-slate-500 hover:bg-slate-100" aria-label="Close menu"><X className="h-5 w-5" /></button>
            <SidebarContent role={role} onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}
      <div className="lg:pl-60">
        <header className="no-print sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
          <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 px-4 sm:px-8">
            <div className="flex items-center gap-3">
              <button onClick={() => setOpen(true)} className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden" aria-label="Open menu"><Menu className="h-5 w-5" /></button>
              <span className="lg:hidden"><Logo size="sm" to={role === "recruiter" ? "/recruiter" : "/jobs"} /></span>
            </div>
            <UserMenu />
          </div>
        </header>
        <VerifyBanner />
        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-8 lg:py-8">
          <div key={pathname} className="animate-page-in">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}

export function RecruiterLayout() {
  return <PortalLayout role="recruiter" />;
}

export function CandidateLayout() {
  return <PortalLayout role="candidate" />;
}

/** Interview: nothing on screen but the interview itself. */
export function FocusLayout() {
  return (
    <div className="dot-canvas min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Logo size="sm" to="/applications" />
          <Link to="/applications" className="text-sm font-medium text-slate-500 hover:text-slate-900">Back to my applications</Link>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-4 sm:px-6">
        <Outlet />
      </main>
    </div>
  );
}

/* ---------------------------------------------------------------- Public pages */

export function PublicLayout() {
  return (
    <div className="min-h-screen bg-white">
      <Outlet />
    </div>
  );
}
