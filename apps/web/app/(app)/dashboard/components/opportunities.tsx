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

      </div>

      <div className="px-5 py-8 text-sm leading-6 text-[#8D9AAA]">
        Job discovery is not connected yet. No opportunities are being shown.
      </div>

      <div className="border-t border-[#1A3048] px-5 py-4 font-mono text-[9px] uppercase tracking-wider text-[#5E7187]">
        Job discovery engine coming online in later intelligence modules.
      </div>
    </section>
  );
}