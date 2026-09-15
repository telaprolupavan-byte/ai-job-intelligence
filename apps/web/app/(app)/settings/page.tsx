import Link from "next/link";

export default function Page() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#05070A] px-6 text-[#F2F5F8]">
      <div className="w-full max-w-lg border border-[#1A3048] bg-[#0B1626] p-8">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-[#E50920]">
          Intelligence Module
        </div>

        <h1 className="mt-4 text-4xl font-bold tracking-tight">
          Coming Soon
        </h1>

        <p className="mt-4 text-sm leading-7 text-[#8D9AAA]">
          This module is part of the AI Job Intelligence roadmap and will be
          activated in a future feature release.
        </p>

        <div className="mt-6 border-t border-[#1A3048] pt-5">
          <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-[#1677E8]">
            SYSTEM / MODULE OFFLINE
          </div>
        </div>

        <Link
          href="/dashboard"
          className="mt-7 inline-flex bg-[#E50920] px-5 py-3 text-xs font-bold uppercase tracking-[0.15em] text-white transition hover:bg-[#FF1E32]"
        >
          ← Back to Dashboard
        </Link>
      </div>
    </main>
  );
}
