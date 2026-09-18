"use client";

import Link from "next/link";
import { Suspense, FormEvent, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { login } from "@/lib/auth";
import AppButton from "@/components/app/app-button";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const registered = searchParams.get("registered") === "true";
  const resetSuccess = searchParams.get("reset") === "true";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setError("");
    setLoading(true);

    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to sign in.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-app-bg px-6 py-10 text-app-text">
      <div className="mx-auto flex min-h-[85vh] max-w-6xl items-center justify-center">
        <div className="w-full max-w-md">
          <div className="mb-10">
            <p className="mono mb-4 text-xs uppercase tracking-[0.25em] text-app-red">
              02 / AUTHENTICATION
            </p>

            <h1 className="font-[family-name:var(--font-display)] text-4xl font-bold tracking-tight sm:text-5xl">
              Welcome back.
            </h1>

            <p className="mt-5 text-sm leading-6 text-app-muted">
              Access your personalized job intelligence workspace.
            </p>
          </div>

          <div className="rounded-[18px] border border-app-border bg-app-panel p-8 sm:p-10">
            <div className="mb-6">
              <div className="font-[family-name:var(--font-display)] text-2xl font-bold text-app-text">
                NERO
              </div>

              <h2 className="mt-4 text-lg font-bold text-app-text">
                Sign in to your intelligence workspace
              </h2>

              <p className="mt-2 text-xs leading-5 text-app-muted">
                Your resume, jobs, matches, and applications in one place.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label
                  htmlFor="email"
                  className="mono mb-2 block text-xs uppercase tracking-wider text-app-muted"
                >
                  Email
                </label>

                <input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="w-full rounded-[9px] border border-app-border bg-app-panel px-4 py-3 text-sm outline-none transition focus:border-app-blue"
                  placeholder="you@example.com"
                />
              </div>

              <div>
                <label
                  htmlFor="password"
                  className="mono mb-2 block text-xs uppercase tracking-wider text-app-muted"
                >
                  Password
                </label>

                <input
                  id="password"
                  type="password"
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="w-full rounded-[9px] border border-app-border bg-app-panel px-4 py-3 text-sm outline-none transition focus:border-app-blue"
                  placeholder="Enter your password"
                />

                <div className="mt-2 text-right">
                  <Link
                    href="/forgot-password"
                    className="text-xs text-app-muted underline underline-offset-4 hover:text-app-red"
                  >
                    Forgot password?
                  </Link>
                </div>
              </div>

              {registered && (
                <div
                  role="status"
                  className="rounded-lg border border-app-border bg-app-surface px-4 py-3 text-sm"
                >
                  Account created. Sign in to continue.
                </div>
              )}

              {resetSuccess && (
                <div
                  role="status"
                  className="rounded-lg border border-app-border bg-app-surface px-4 py-3 text-sm"
                >
                  Password reset. Sign in with your new password.
                </div>
              )}

              {error && (
                <div
                  role="alert"
                  className="rounded-lg border border-app-red/40 bg-app-red/10 px-4 py-3 text-sm"
                >
                  {error}
                </div>
              )}

              <AppButton
                type="submit"
                loading={loading}
                className="w-full normal-case tracking-normal"
              >
                Sign in
              </AppButton>
            </form>

            <p className="mt-6 text-center text-sm text-app-muted">
              New to NERO?{" "}
              <Link
                href="/register"
                className="text-app-text underline underline-offset-4 hover:text-app-red"
              >
                Create an account
              </Link>
            </p>
          </div>

          <p className="mt-6 text-center text-xs leading-5 text-app-muted">
            Your decisions remain under your control. NERO does not
            auto-apply.
          </p>
        </div>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center bg-app-bg text-app-text">
          <p className="mono text-xs uppercase tracking-widest text-app-muted">
            LOADING...
          </p>
        </main>
      }
    >
      <LoginForm />
    </Suspense>
  );
}