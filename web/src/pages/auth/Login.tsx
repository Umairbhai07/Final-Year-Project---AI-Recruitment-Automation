import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";
import { errorMessage } from "../../api/client";
import type { Role } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { homeFor } from "../../auth/ProtectedRoute";
import { AuthShell } from "../../components/AuthShell";
import { Alert, Field, PasswordInput, Segmented, TextInput } from "../../components/form";
import { Button } from "../../components/ui";

const schema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});
type Form = z.infer<typeof schema>;

const DEMO: Record<Role, string> = { recruiter: "recruiter@demo.com", candidate: "candidate5@demo.com" };
// Demo shortcuts show while developing. In production they only appear when VITE_SHOW_DEMO=true (e.g. for the viva).
const SHOW_DEMO = import.meta.env.DEV || import.meta.env.VITE_SHOW_DEMO === "true";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const [role, setRole] = useState<Role>(params.get("role") === "recruiter" ? "recruiter" : "candidate");
  const [serverError, setServerError] = useState<string | null>(null);
  const expired = params.get("expired") === "1";
  const { register, handleSubmit, setValue, formState: { errors, isSubmitting } } = useForm<Form>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: Form) => {
    setServerError(null);
    try {
      const user = await login(values.email, values.password, role);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from && from !== "/login" ? from : homeFor(user.role), { replace: true });
    } catch (err) {
      setServerError(errorMessage(err));
    }
  };

  const fillDemo = () => {
    setValue("email", DEMO[role], { shouldValidate: true });
    setValue("password", "Demo1234", { shouldValidate: true });
  };

  return (
    <AuthShell role={role}>
      <h1 className="font-display text-3xl font-bold tracking-[-0.03em] text-neutral-950">Welcome back</h1>
      <p className="mt-1.5 text-sm text-slate-500">Sign in to continue. Choose your account type first.</p>

      <div className="mt-6">
        <Segmented
          full
          label="Account type"
          value={role}
          onChange={(r) => { setRole(r); setServerError(null); }}
          options={[
            { value: "candidate", label: "Candidate" },
            { value: "recruiter", label: "Recruiter" },
          ]}
        />
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="mt-5 space-y-4" noValidate>
        {expired && !serverError && <Alert tone="info">Your session expired. Please sign in again.</Alert>}
        {serverError && <Alert>{serverError}</Alert>}
        <Field label="Email" htmlFor="email" error={errors.email?.message}>
          <TextInput id="email" type="email" autoComplete="email" placeholder="you@company.com" invalid={!!errors.email} {...register("email")} />
        </Field>
        <div>
          <Field label="Password" htmlFor="password" error={errors.password?.message}>
            <PasswordInput id="password" autoComplete="current-password" placeholder="Your password" invalid={!!errors.password} {...register("password")} />
          </Field>
          <div className="mt-2 text-right"><Link to="/forgot-password" className="text-sm font-medium text-slate-600 hover:text-slate-900">Forgot password?</Link></div>
        </div>
        <Button type="submit" size="lg" className="w-full" loading={isSubmitting}>
          Sign in
        </Button>
        {SHOW_DEMO && (
          <Button type="button" variant="secondary" className="w-full" onClick={fillDemo}>
            Use the demo {role} account
          </Button>
        )}
      </form>

      <p className="mt-6 text-center text-sm text-slate-500">
        New here? <Link to={`/register?role=${role}`} className="font-semibold text-neutral-950 underline-offset-4 hover:underline">Create an account</Link>
      </p>
    </AuthShell>
  );
}
