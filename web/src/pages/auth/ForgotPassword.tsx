import { zodResolver } from "@hookform/resolvers/zod";
import { Lock } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";
import { errorMessage } from "../../api/client";
import { authApi } from "../../api/endpoints";
import { AuthShell } from "../../components/AuthShell";
import { Alert, CodeInput, Field, PasswordInput, PasswordStrength, TextInput } from "../../components/form";
import { Button } from "../../components/ui";

const schema = z.object({ email: z.string().min(1, "Email is required").email("Enter a valid email address") });
type Form = z.infer<typeof schema>;

/** Forgot password: the email gets a 6-digit code, then the code and a new password are entered here. */
export default function ForgotPassword() {
  const navigate = useNavigate();
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Form>({ resolver: zodResolver(schema) });

  const send = async (email: string) => {
    setServerError(null);
    try {
      await authApi.forgotPassword(email);
      setSentTo(email);
    } catch (err) {
      setServerError(errorMessage(err));
    }
  };

  const reset = async (e: FormEvent) => {
    e.preventDefault();
    if (!sentTo) return;
    const problem = code.length !== 6 ? "Enter the 6-digit code from the email"
      : pw.length < 8 ? "Use at least 8 characters for the new password"
      : !/\d/.test(pw) ? "Include at least one number in the new password"
      : pw !== confirm ? "Passwords do not match" : null;
    if (problem) return setServerError(problem);
    setServerError(null); setBusy(true);
    try {
      await authApi.resetWithCode(sentTo, code, pw);
      toast.success("Password changed. Sign in with your new password.");
      navigate("/login", { replace: true });
    } catch (err) {
      setServerError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell role="candidate">
      {sentTo ? (
        <>
          <h1 className="font-display text-3xl font-bold tracking-[-0.03em] text-neutral-950">Enter your code</h1>
          <p className="mt-2 text-sm text-slate-500">
            If an account exists for <b className="text-slate-700">{sentTo}</b>, we've emailed a 6-digit code. It works for
            10 minutes. Check your spam folder too.
          </p>
          <form onSubmit={reset} className="mt-7 space-y-5" noValidate autoComplete="off">
            {serverError && <Alert>{serverError}</Alert>}
            <Field label="Code" htmlFor="code">
              <CodeInput id="code" value={code} onChange={setCode} autoFocus />
            </Field>
            <Field label="New password" htmlFor="new-password">
              <PasswordInput id="new-password" autoComplete="new-password" icon={<Lock />} value={pw} onChange={(e) => setPw(e.target.value)} />
              <PasswordStrength password={pw} />
            </Field>
            <Field label="Confirm new password" htmlFor="confirm-password">
              <PasswordInput id="confirm-password" autoComplete="new-password" icon={<Lock />} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            </Field>
            <Button type="submit" size="lg" className="w-full" loading={busy}>Change password</Button>
          </form>
          <div className="mt-4 flex justify-between text-sm">
            <button type="button" className="link" onClick={() => send(sentTo)}>Send a new code</button>
            <button type="button" className="link" onClick={() => { setSentTo(null); setCode(""); setServerError(null); }}>Use a different email</button>
          </div>
        </>
      ) : (
        <>
          <h1 className="font-display text-3xl font-bold tracking-[-0.03em] text-neutral-950">Forgot your password?</h1>
          <p className="mt-2 text-sm text-slate-500">Enter the email you signed up with and we'll send you a 6-digit code.</p>
          <form onSubmit={handleSubmit(({ email }) => send(email.trim().toLowerCase()))} className="mt-7 space-y-5" noValidate>
            {serverError && <Alert>{serverError}</Alert>}
            <Field label="Email" htmlFor="email" error={errors.email?.message}>
              <TextInput id="email" type="email" autoComplete="email" placeholder="you@example.com" invalid={!!errors.email} {...register("email")} />
            </Field>
            <Button type="submit" size="lg" className="w-full" loading={isSubmitting}>Send code</Button>
          </form>
        </>
      )}
      <p className="mt-8 text-center text-sm text-slate-500">
        <Link to="/login" className="link inline-flex items-center gap-1">Back to sign in</Link>
      </p>
    </AuthShell>
  );
}
