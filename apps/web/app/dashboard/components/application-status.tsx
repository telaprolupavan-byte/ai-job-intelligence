type Props = {
  applications: {
    applied: number;
    in_review: number;
    interview: number;
    offers: number;
  };
};

export default function ApplicationStatus({ applications }: Props) {
  const total =
    applications.applied +
    applications.in_review +
    applications.interview +
    applications.offers;

  const statuses = [
    ["Applied", applications.applied],
    ["In Review", applications.in_review],
    ["Interview", applications.interview],
    ["Offers", applications.offers],
  ];

  return (
    <section className="border border-[#1A3048] bg-[#0B1626] p-5">
      <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-[#5E7187]">
        Application Status
      </div>

      <div className="mt-6 flex items-center gap-8">
        <div className="relative flex h-28 w-28 shrink-0 items-center justify-center rounded-full border-[8px] border-[#173454]">
          <div className="text-center">
            <div className="text-2xl font-bold text-[#F2F5F8]">{total}</div>
            <div className="font-mono text-[8px] uppercase tracking-wider text-[#5E7187]">
              Total
            </div>
          </div>
        </div>

        <div className="flex-1 space-y-3">
          {statuses.map(([label, value], index) => (
            <div
              key={label}
              className="flex items-center justify-between text-xs"
            >
              <div className="flex items-center gap-2 text-[#8D9AAA]">
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    index % 2 === 0 ? "bg-[#E50920]" : "bg-[#1677E8]"
                  }`}
                />
                {label}
              </div>

              <span className="font-mono text-[#F2F5F8]">{value}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}