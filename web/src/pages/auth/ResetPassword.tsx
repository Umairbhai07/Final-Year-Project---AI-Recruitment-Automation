import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";
import { errorMessage } from "../../api/client";
import { authApi } from "../../api/endpoints";
import { AuthShell } from "../../components/AuthShell";
import { Alert, Field, PasswordInput, PasswordStrength } from "../../components/form";
import { Button } from "../../components/ui";

const schema = z
  .object({
    password: z.string().min(8, "Use at least 8 characters").regex(/\d/, "Include at least one number"),
    confirm: z.string().min(1, "Please confirm your password"),
  })
  .refine((v) => v.password === v.confirm, { path: ["confirm"], message: "Passwords do not match" });
type Form = z.infer<typeof schema>;

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();
  const [serverError, setServerError] = useState<string | null>(null);
  const { register, handleSubmit, watch, formState: { errors, isSubmitting } } = useForm<Form>({ resolver: zodResolver(schema) });
  const password = watch("password") ?? "";

  const onSubmit = async (v: Form) => {
    setServerError(null);
    try {
      await authApi.resetPassword(token, v.password);
      toast.success("Password changed. Please sign in with your new password.");
      navigate("/login", { replace: true });
    } catch (err) {
      setServerError(errorMessage(err));
    }
  };

  return (
    <AuthShell role="candidate">
      <h1 className="font-display text-3xl font-bold tracking-[-0.03em] text-neutral-950">Choose a new password</h1>
      <p className="mt-2 text-sm text-slate-500">You'll be signed out on all other devices.</p>
      {!token ? (
        <div className="mt-7"><Alert>This link is incomplete. Open the link from the email again, or <Link to="/forgot-password" className="link">ask for a new one</Link>.</Alert></div>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="mt-7 space-y-5" noValidate>
          {serverError && <Alert>{serverError} <Link to="/forgot-password" className="link">Send a new link</Link></Alert>}
          <Field label="New password" htmlFor="password" error={errors.password?.message}>
            <PasswordInput id="password" autoComplete="new-password" placeholder="At least 8 characters and a number" invalid={!!errors.password} {...register("password")} />
            <PasswordStrength password={password} />
          </Field>
          <Field label="Confirm new password" htmlFor="confirm" error={errors.confirm?.message}>
            <PasswordInput id="confirm" autoComplete="new-password" placeholder="Type it again" invalid={!!errors.confirm} {...register("confirm")} />
          </Field>
          <Button type="submit" size="lg" className="w-full" loading={isSubmitting}>Save new password</Button>
        </form>
      )}
    </AuthShell>
  );
}
