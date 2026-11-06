import { CheckCircle2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { authApi } from "../../api/endpoints";
import { useAuth } from "../../auth/AuthContext";
import { homeFor } from "../../auth/ProtectedRoute";
import { AuthShell } from "../../components/AuthShell";
import { Alert } from "../../components/form";
import { Spinner } from "../../components/ui";

/** Opened from the "Confirm your email" link. Works whether or not the person is signed in. */
export default function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const { user, refreshUser } = useAuth();
  const [state, setState] = useState<"working" | "done" | "error">(token ? "working" : "error");
  const [error, setError] = useState(token ? "" : "This link is incomplete. Open the link from the email again.");
  const sent = useRef(false);

  useEffect(() => {
    if (!token || sent.current) return;
    sent.current = true;
    authApi.verifyEmail(token)
      .then(async () => {
        setState("done");
        if (user) await refreshUser();
      })
      .catch((e) => { setState("error"); setError(errorMessage(e)); });
  }, [token, user, refreshUser]);

  return (
    <AuthShell role={user?.role ?? "candidate"}>
      <h1 className="font-display text-3xl font-bold tracking-[-0.03em] text-neutral-950">Confirm your email</h1>
      <div className="mt-7">
        {state === "working" && <div className="flex items-center gap-3 text-sm text-slate-600"><Spinner className="h-5 w-5" /> Checking your link…</div>}
        {state === "done" && (
          <div className="space-y-5">
            <p className="flex items-center gap-2 text-sm font-medium text-emerald-700"><CheckCircle2 className="h-5 w-5" /> Your email is confirmed.</p>
            <Link to={user ? homeFor(user.role) : "/login"} className="link text-sm font-semibold">{user ? "Continue" : "Sign in"}</Link>
          </div>
        )}
        {state === "error" && (
          <Alert>{error} {user ? "You can send a new link from the banner at the top of the app." : <Link to="/login" className="link">Sign in to send a new link</Link>}</Alert>
        )}
      </div>
    </AuthShell>
  );
}
