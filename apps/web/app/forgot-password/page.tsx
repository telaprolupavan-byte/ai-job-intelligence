"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { forgotPassword } from "@/lib/auth";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setError("");
    setLoading(true);

    try {
      await forgotPassword(email);
      setSubmitted(true);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to process your request.",
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
              Reset your password.
            </h1>

            <p className="mt-5 text-sm leading-6 text-app-muted">
              Enter the email associated with your account and we will
              send you a link to reset your password.
            </p>
          </div>

          {submitted ? (
            <div
              role="status"
              className="rounded-lg border border-app-border bg-app-surface px-4 py-3 text-sm"
            >
              If that email is registered, a password reset link has been
              sent. Check your inbox for further instructions.
            </div>
          ) : (
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
                {loading ? "SENDING..." : "SEND RESET LINK →"}
              </button>
            </form>
          )}

          <p className="mt-8 text-center text-sm text-app-muted">
            Remembered your password?{" "}
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
