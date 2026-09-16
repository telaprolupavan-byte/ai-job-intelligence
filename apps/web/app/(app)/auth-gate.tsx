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
      <main className="flex min-h-screen items-center justify-center bg-[#05070A] text-[#1677E8]">
        <div className="font-mono text-xs uppercase tracking-[0.25em]">
          Verifying session...
        </div>
      </main>
    );
  }

  return children;
}