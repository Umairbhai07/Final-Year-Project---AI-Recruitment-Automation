import { Compass } from "lucide-react";
import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-canvas px-4 text-center">
      <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-50 text-brand-600"><Compass className="h-8 w-8" /></span>
      <p className="mt-6 eyebrow">Error 404</p>
      <h1 className="mt-2 text-3xl font-extrabold text-slate-900">Page not found</h1>
      <p className="mt-2 max-w-sm text-slate-500">The page you're looking for doesn't exist or has moved.</p>
      <Link to="/" className="mt-8 rounded-xl bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lift hover:bg-brand-700">Go to home page</Link>
    </main>
  );
}
