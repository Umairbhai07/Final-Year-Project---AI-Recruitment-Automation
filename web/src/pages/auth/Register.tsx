import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";
import { errorMessage } from "../../api/client";
import { authApi } from "../../api/endpoints";
import type { Role } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { homeFor } from "../../auth/ProtectedRoute";
import { AuthShell } from "../../components/AuthShell";
import { Alert, Field, PasswordInput, PasswordStrength, Segmented, TextInput } from "../../components/form";
import { Button } from "../../components/ui";

const schema = z
  .object({
    full_name: z.string().trim().min(2, "Enter your full name"),
    email: z.string().min(1, "Email is required").email("Enter a valid email address"),
    password: z.string().min(8, "Use at least 8 characters").regex(/\d/, "Include at least one number"),
    confirm: z.string().min(1, "Please confirm your password"),
    role: z.enum(["recruiter", "candidate"]),
  })
  .refine((v) => v.password === v.confirm, { path: ["confirm"], message: "Passwords do not match" });
type Form = z.infer<typeof schema>;

export default function Register() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [serverError, setServerError] = useState<string | null>(null);
  const { register, handleSubmit, watch, setValue, formState: { errors, isSubmitting } } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { role: params.get("role") === "recruiter" ? "recruiter" : "candidate" },
  });
  const role = watch("role") as Role;
  const password = watch("password") ?? "";

  const onSubmit = async (v: Form) => {
    setServerError(null);
    try {
      await authApi.register({ full_name: v.full_name, email: v.email, password: v.password, role: v.role });
      const user = await login(v.email, v.password, v.role);
      toast.success(`Welcome, ${user.full_name.split(" ")[0]}! Your account is ready.`);
      navigate(user.role === "candidate" ? "/profile?welcome=1" : homeFor(user.role), { replace: true });
    } catch (err) {
      setServerError(errorMessage(err));
    }
  };

  return (
    <AuthShell role={role}>
      <h1 className="font-display text-3xl font-bold tracking-[-0.03em] text-neutral-950">Create your account</h1>
      <p className="mt-1.5 text-sm text-slate-500">Get started in less than a minute.</p>

      <form onSubmit={handleSubmit(onSubmit)} className="mt-6 space-y-4" noValidate>
        <Segmented
          full
          label="Account type"
          value={role}
          onChange={(r) => setValue("role", r)}
          options={[
            { value: "candidate", label: "I'm looking for a job" },
            { value: "recruiter", label: "I'm hiring" },
          ]}
        />

        {serverError && <Alert>{serverError}</Alert>}
        <Field label="Full name" htmlFor="full_name" error={errors.full_name?.message}>
          <TextInput id="full_name" autoComplete="name" placeholder="Your name" invalid={!!errors.full_name} {...register("full_name")} />
        </Field>
        <Field label={role === "recruiter" ? "Work email" : "Email"} htmlFor="email" error={errors.email?.message}>
          <TextInput id="email" type="email" autoComplete="email" placeholder="you@company.com" invalid={!!errors.email} {...register("email")} />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Password" htmlFor="password" error={errors.password?.message}>
            <PasswordInput id="password" autoComplete="new-password" placeholder="8+ characters" invalid={!!errors.password} {...register("password")} />
          </Field>
          <Field label="Confirm password" htmlFor="confirm" error={errors.confirm?.message}>
            <PasswordInput id="confirm" autoComplete="new-password" placeholder="Type it again" invalid={!!errors.confirm} {...register("confirm")} />
          </Field>
        </div>
        {!errors.password && password && <PasswordStrength password={password} />}
        <Button type="submit" size="lg" className="w-full" loading={isSubmitting}>Create account</Button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-500">
        Already have an account? <Link to={`/login?role=${role}`} className="font-semibold text-neutral-950 underline-offset-4 hover:underline">Sign in</Link>
      </p>
    </AuthShell>
  );
}
