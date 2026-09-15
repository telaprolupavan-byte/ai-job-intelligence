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
    <main className="min-h-screen bg-background px-6 py-10 text-foreground">
      <div className="mx-auto flex min-h-[85vh] max-w-6xl items-center justify-center">
        <div className="w-full max-w-md">
          <div className="mb-10">
            <p className="mono mb-4 text-xs uppercase tracking-[0.25em] text-primary">
              01 / CREATE ACCOUNT
            </p>

            <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
              START YOUR
              <br />
              JOB INTELLIGENCE.
            </h1>

            <p className="mt-5 text-sm leading-6 text-muted-foreground">
              Create your account to build your personalized job search,
              resume intelligence, and application workflow.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label
                htmlFor="email"
                className="mono mb-2 block text-xs uppercase tracking-wider text-muted-foreground"
              >
                Email
              </label>

              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="w-full border border-border bg-surface px-4 py-3 text-sm outline-none transition focus:border-primary"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="mono mb-2 block text-xs uppercase tracking-wider text-muted-foreground"
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
                className="w-full border border-border bg-surface px-4 py-3 text-sm outline-none transition focus:border-primary"
                placeholder="Minimum 8 characters"
              />
            </div>

            <div>
              <label
                htmlFor="confirm-password"
                className="mono mb-2 block text-xs uppercase tracking-wider text-muted-foreground"
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
                className="w-full border border-border bg-surface px-4 py-3 text-sm outline-none transition focus:border-primary"
                placeholder="Repeat your password"
              />
            </div>

            {error && (
              <div className="border border-primary/40 bg-primary/10 px-4 py-3 text-sm text-foreground">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-primary px-5 py-3 text-sm font-medium text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? "CREATING ACCOUNT..." : "CREATE ACCOUNT →"}
            </button>
          </form>

          <p className="mt-8 text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link
              href="/login"
              className="text-foreground underline underline-offset-4 hover:text-primary"
            >
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}