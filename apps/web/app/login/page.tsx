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
    <main className="min-h-screen bg-background px-6 py-10 text-foreground">
      <div className="mx-auto flex min-h-[85vh] max-w-6xl items-center justify-center">
        <div className="w-full max-w-md">
          <div className="mb-10">
            <p className="mono mb-4 text-xs uppercase tracking-[0.25em] text-primary">
              02 / AUTHENTICATION
            </p>

            <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
              WELCOME
              <br />
              BACK.
            </h1>

            <p className="mt-5 text-sm leading-6 text-muted-foreground">
              Access your personalized job intelligence workspace.
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
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full border border-border bg-surface px-4 py-3 text-sm outline-none transition focus:border-primary"
                placeholder="Your password"
              />
            </div>

            {registered && (
              <div className="border border-border bg-surface px-4 py-3 text-sm">
                Account created. Sign in to continue.
              </div>
            )}

            {error && (
              <div className="border border-primary/40 bg-primary/10 px-4 py-3 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-primary px-5 py-3 text-sm font-medium text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? "AUTHENTICATING..." : "SIGN IN →"}
            </button>
          </form>

          <p className="mt-8 text-center text-sm text-muted-foreground">
            Do not have an account?{" "}
            <Link
              href="/register"
              className="text-foreground underline underline-offset-4 hover:text-primary"
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
        <main className="flex min-h-screen items-center justify-center bg-background text-foreground">
          <p className="mono text-xs uppercase tracking-widest text-muted-foreground">
            LOADING...
          </p>
        </main>
      }
    >
      <LoginForm />
    </Suspense>
  );
}