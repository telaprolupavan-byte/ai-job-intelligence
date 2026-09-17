"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { getCurrentUser } from "@/lib/auth";

export default function AuthGate({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    let mounted = true;

    getCurrentUser()
      .then(() => {
        if (mounted) {
          setAuthorized(true);
        }
      })
      .catch(() => {
        if (mounted) {
          router.replace("/login");
        }
      });

    return () => {
      mounted = false;
    };
  }, [router]);

  if (!authorized) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-app-bg text-app-blue">
        <div
          role="status"
          className="flex items-center gap-3 font-mono text-xs uppercase tracking-[0.25em]"
        >
          <span
            aria-hidden="true"
            className="h-2 w-2 animate-pulse rounded-full bg-app-blue"
          />
          Verifying session...
        </div>
      </main>
    );
  }

  return children;
}
