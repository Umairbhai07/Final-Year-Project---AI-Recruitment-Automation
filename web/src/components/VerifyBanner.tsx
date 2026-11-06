import { useState } from "react";
import toast from "react-hot-toast";
import { errorMessage } from "../api/client";
import { authApi } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";

/** Shown while email confirmation is switched on and this account has not confirmed yet. */
export function VerifyBanner() {
  const { user } = useAuth();
  const [sending, setSending] = useState(false);
  if (!user?.must_verify) return null;
  const resend = async () => {
    setSending(true);
    try {
      await authApi.resendVerification();
      toast.success("We sent a new link to your email.");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSending(false);
    }
  };
  return (
    <div className="no-print border-b border-amber-200 bg-amber-50">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-sm text-amber-900 sm:px-8">
        <span>Please confirm your email address <b>{user.email}</b>. Open the link we emailed you.</span>
        <button onClick={resend} disabled={sending} className="font-semibold underline underline-offset-2 disabled:opacity-60">
          {sending ? "Sending…" : "Send the link again"}
        </button>
      </div>
    </div>
  );
}
