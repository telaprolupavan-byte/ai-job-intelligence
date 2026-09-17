"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { register } from "@/lib/auth";

export default function RegisterPage() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);

    try {
      await register(email, password);
      router.push("/login?registered=true");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to create your account.",
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
              01 / CREATE ACCOUNT
            </p>

            <h1 className="font-[family-name:var(--font-display)] text-4xl font-bold tracking-tight sm:text-5xl">
              Start your job intelligence.
            </h1>

            <p className="mt-5 text-sm leading-6 text-app-muted">
              Create your account to build your personalized job search,
              resume intelligence, and application workflow.
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
                minLength={8}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full rounded-lg border border-app-border-strong bg-app-bg px-4 py-3 text-sm outline-none transition focus:border-app-blue"
                placeholder="Minimum 8 characters"
              />
            </div>

            <div>
              <label
                htmlFor="confirm-password"
                className="mono mb-2 block text-xs uppercase tracking-wider text-app-muted"
              >
                Confirm Password
              </label>

              <input
                id="confirm-password"
                type="password"
                required
                minLength={8}
                value={confirmPassword}
                onChange={(event) =>
                  setConfirmPassword(event.target.value)
                }
                className="w-full rounded-lg border border-app-border-strong bg-app-bg px-4 py-3 text-sm outline-none transition focus:border-app-blue"
                placeholder="Repeat your password"
              />
            </div>

            {error && (
              <div
                role="alert"
                className="rounded-lg border border-app-red/40 bg-app-red/10 px-4 py-3 text-sm text-app-text"
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-crimson-fill px-5 py-3 text-sm font-medium text-white transition hover:bg-crimson-fill-hover disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? "CREATING ACCOUNT..." : "CREATE ACCOUNT →"}
            </button>
          </form>

          <p className="mt-8 text-center text-sm text-app-muted">
            Already have an account?{" "}
            <Link
              href="/login"
              className="text-app-text underline underline-offset-4 hover:text-app-red"
            >
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}