import { Lock, MailCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import toast from "react-hot-toast";
import { errorMessage } from "../api/client";
import { authApi } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { Alert, CodeInput, Field, PasswordInput, PasswordStrength } from "./form";
import { Button, Modal } from "./ui";

function passwordProblem(pw: string, confirm: string): string | null {
  if (pw.length < 8) return "Use at least 8 characters";
  if (!/\d/.test(pw)) return "Include at least one number";
  if (pw !== confirm) return "Passwords do not match";
  return null;
}

/** Two steps: the current password, then the 6-digit code from the email together with the new password. */
export function ChangePasswordModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { user } = useAuth();
  const [step, setStep] = useState<"current" | "code">("current");
  const [current, setCurrent] = useState("");
  const [code, setCode] = useState("");
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const close = () => {
    setStep("current"); setCurrent(""); setCode(""); setPw(""); setConfirm(""); setError(null);
    onClose();
  };

  const sendCode = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!current) return setError("Enter your current password");
    setError(null); setBusy(true);
    try {
      await authApi.sendChangeCode(current);
      setStep("code");
      toast.success("Code sent to your email");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const save = async (e?: FormEvent) => {
    e?.preventDefault();
    if (code.length !== 6) return setError("Enter the 6-digit code from the email");
    const problem = passwordProblem(pw, confirm);
    if (problem) return setError(problem);
    setError(null); setBusy(true);
    try {
      await authApi.changePassword(code, pw);
      toast.success("Password changed. Other devices have been signed out.");
      close();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} onClose={close} title="Change password"
      footer={<>
        <Button variant="secondary" onClick={close}>Cancel</Button>
        {step === "current"
          ? <Button loading={busy} onClick={() => sendCode()}>Send code</Button>
          : <Button loading={busy} onClick={() => save()}>Save password</Button>}
      </>}>
      {step === "current" ? (
        <form onSubmit={sendCode} className="space-y-4" noValidate autoComplete="off">
          {error && <Alert>{error}</Alert>}
          <p>First confirm it's you. We'll email a 6-digit code to <b className="text-slate-800">{user?.email}</b>.</p>
          <Field label="Current password" htmlFor="cp-current">
            <PasswordInput id="cp-current" name="cp-current" autoComplete="new-password" icon={<Lock />}
              value={current} onChange={(e) => setCurrent(e.target.value)} />
          </Field>
          <button type="submit" className="hidden" />
        </form>
      ) : (
        <form onSubmit={save} className="space-y-4" noValidate autoComplete="off">
          {error && <Alert>{error}</Alert>}
          <div className="flex items-start gap-2.5 border border-slate-200 bg-slate-50 px-3.5 py-3 text-slate-700">
            <MailCheck className="mt-0.5 h-4 w-4 shrink-0" />
            <span>We sent a code to <b>{user?.email}</b>. It works for 10 minutes. Check spam too.</span>
          </div>
          <Field label="Code from the email" htmlFor="cp-code">
            <CodeInput id="cp-code" value={code} onChange={setCode} />
          </Field>
          <Field label="New password" htmlFor="cp-new">
            <PasswordInput id="cp-new" name="cp-new" autoComplete="new-password" icon={<Lock />} value={pw} onChange={(e) => setPw(e.target.value)} />
            <PasswordStrength password={pw} />
          </Field>
          <Field label="Confirm new password" htmlFor="cp-confirm">
            <PasswordInput id="cp-confirm" name="cp-confirm" autoComplete="new-password" icon={<Lock />} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </Field>
          <button type="button" onClick={() => sendCode()} disabled={busy} className="text-sm font-medium text-slate-700 underline">Send a new code</button>
          <button type="submit" className="hidden" />
        </form>
      )}
    </Modal>
  );
}
