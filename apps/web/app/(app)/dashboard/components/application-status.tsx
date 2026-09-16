type Props = {
  applications: {
    available: boolean;
  };
};

export default function ApplicationStatus({ applications }: Props) {
  return (
    <section className="border border-[#1A3048] bg-[#0B1626] p-5">
      <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-[#5E7187]">
        Application Status
      </div>

      <div className="mt-6 border border-[#1A3048] bg-[#05070A] p-5 text-sm leading-6 text-[#8D9AAA]">
        {applications.available
          ? "Application tracking data is available."
          : "Application tracking is not available yet."}
      </div>
    </section>
  );
}