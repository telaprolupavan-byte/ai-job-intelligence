"use client";

import Link from "next/link";
import { Suspense, FormEvent, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { login } from "@/lib/auth";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const registered = searchParams.get("registered") === "true";

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
                className="w-full rounded-lg border border-app-border-strong bg-app-bg px-4 py-3 text-sm outline-none transition focus:border-app-blue"
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
                className="w-full rounded-lg border border-app-border-strong bg-app-bg px-4 py-3 text-sm outline-none transition focus:border-app-blue"
                placeholder="Your password"
              />
            </div>

            {registered && (
              <div
                role="status"
                className="rounded-lg border border-app-border bg-app-surface px-4 py-3 text-sm"
              >
                Account created. Sign in to continue.
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

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-crimson-fill px-5 py-3 text-sm font-medium text-white transition hover:bg-crimson-fill-hover disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? "AUTHENTICATING..." : "SIGN IN →"}
            </button>
          </form>

          <p className="mt-8 text-center text-sm text-app-muted">
            Do not have an account?{" "}
            <Link
              href="/register"
              className="text-app-text underline underline-offset-4 hover:text-app-red"
            >
              Create account
            </Link>
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