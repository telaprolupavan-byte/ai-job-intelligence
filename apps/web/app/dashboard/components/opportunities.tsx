import Link from "next/link";

const opportunities = [
  {
    title: "AI / ML ENGINEER",
    company: "Opportunity Intelligence",
    match: "—",
  },
  {
    title: "MACHINE LEARNING ENGINEER",
    company: "Opportunity Intelligence",
    match: "—",
  },
  {
    title: "DATA SCIENTIST",
    company: "Opportunity Intelligence",
    match: "—",
  },
];

export default function Opportunities() {
  return (
    <section className="border border-[#1A3048] bg-[#07111F]">
      <div className="flex items-center justify-between border-b border-[#1A3048] px-5 py-4">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-[#5E7187]">
            Today&apos;s Opportunities
          </div>

          <h2 className="mt-1 text-lg font-semibold text-[#F2F5F8]">
            Jobs waiting for intelligence
          </h2>
        </div>

        <Link
          href="/jobs"
          className="font-mono text-[10px] uppercase tracking-wider text-[#1677E8] hover:text-[#FF1E32]"
        >
          View All →
        </Link>
      </div>

      <div className="divide-y divide-[#1A3048]">
        {opportunities.map((job) => (
          <div
            key={job.title}
            className="group flex flex-col gap-4 px-5 py-5 transition hover:bg-[#0B1626] sm:flex-row sm:items-center sm:justify-between"
          >
            <div>
              <div className="text-sm font-semibold text-[#F2F5F8]">
                {job.title}
              </div>

              <div className="mt-1 font-mono text-[10px] uppercase tracking-wider text-[#5E7187]">
                {job.company}
              </div>
            </div>

            <div className="flex items-center gap-5">
              <div className="text-right">
                <div className="font-mono text-[9px] uppercase tracking-wider text-[#5E7187]">
                  Job Match
                </div>

                <div className="mt-1 text-lg font-bold text-[#1677E8]">
                  {job.match}
                </div>
              </div>

              <span className="text-[#E50920] transition group-hover:translate-x-1">
                →
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className="border-t border-[#1A3048] px-5 py-4 font-mono text-[9px] uppercase tracking-wider text-[#5E7187]">
        Job discovery engine coming online in later intelligence modules.
      </div>
    </section>
  );
}