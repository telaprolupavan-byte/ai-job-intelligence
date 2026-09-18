"use client";

import Link from "next/link";
import { Suspense, FormEvent, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { resetPassword } from "@/lib/auth";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (!token) {
      setError("This reset link is invalid. Request a new one.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);

    try {
      await resetPassword(token, password);
      router.push("/login?reset=true");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to reset your password.",
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
              Set a new password.
            </h1>

            <p className="mt-5 text-sm leading-6 text-app-muted">
              Choose a new password for your account.
            </p>
          </div>

          {!token && (
            <div
              role="alert"
              className="mb-5 rounded-lg border border-app-red/40 bg-app-red/10 px-4 py-3 text-sm"
            >
              This reset link is invalid or incomplete. Request a new one
              from the{" "}
              <Link
                href="/forgot-password"
                className="underline underline-offset-4"
              >
                forgot password
              </Link>{" "}
              page.
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label
                htmlFor="password"
                className="mono mb-2 block text-xs uppercase tracking-wider text-app-muted"
              >
                New Password
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
                Confirm New Password
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
                placeholder="Repeat your new password"
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
              disabled={loading || !token}
              className="w-full rounded-lg bg-crimson-fill px-5 py-3 text-sm font-medium text-white transition hover:bg-crimson-fill-hover disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? "RESETTING..." : "RESET PASSWORD →"}
            </button>
          </form>

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

export default function ResetPasswordPage() {
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
      <ResetPasswordForm />
    </Suspense>
  );
}
