"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getCurrentUser, logout, User } from "@/lib/auth";

export default function DashboardPage() {
  const router = useRouter();

  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadUser() {
      try {
        const currentUser = await getCurrentUser();
        setUser(currentUser);
      } catch {
        router.replace("/login");
      } finally {
        setLoading(false);
      }
    }

    loadUser();
  }, [router]);

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background text-foreground">
        <p className="mono text-xs uppercase tracking-widest text-muted-foreground">
          AUTHENTICATING...
        </p>
      </main>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <main className="min-h-screen bg-background px-6 py-10 text-foreground">
      <div className="mx-auto max-w-7xl">
        <header className="flex items-center justify-between border-b border-border pb-6">
          <div>
            <p className="mono text-xs uppercase tracking-[0.25em] text-primary">
              AI JOB INTELLIGENCE
            </p>

            <h1 className="mt-3 text-3xl font-semibold tracking-tight">
              AUTHENTICATED WORKSPACE
            </h1>
          </div>

          <button
            onClick={handleLogout}
            className="border border-border px-4 py-2 text-xs font-medium uppercase tracking-wider transition hover:border-primary hover:text-primary"
          >
            Log Out
          </button>
        </header>

        <section className="mt-12 border border-border bg-surface p-8">
          <p className="mono text-xs uppercase tracking-wider text-muted-foreground">
            SESSION ACTIVE
          </p>

          <h2 className="mt-4 text-2xl font-medium">
            Welcome back.
          </h2>

          <p className="mt-3 text-sm text-muted-foreground">
            {user.email}
          </p>

          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            <div className="border border-border p-5">
              <p className="mono text-xs text-muted-foreground">
                STATUS
              </p>
              <p className="mt-3 text-lg">Authenticated</p>
            </div>

            <div className="border border-border p-5">
              <p className="mono text-xs text-muted-foreground">
                NEXT
              </p>
              <p className="mt-3 text-lg">Profile Setup</p>
            </div>

            <div className="border border-border p-5">
              <p className="mono text-xs text-muted-foreground">
                SYSTEM
              </p>
              <p className="mt-3 text-lg">Online</p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}