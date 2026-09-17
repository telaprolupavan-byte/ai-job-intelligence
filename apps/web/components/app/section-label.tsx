import { cn } from "@/lib/utils";

type SectionLabelProps = {
  children: React.ReactNode;
  tone?: "red" | "blue" | "faint";
  className?: string;
  as?: "div" | "span";
};

const TONE_CLASS = {
  red: "text-app-red",
  blue: "text-app-blue",
  faint: "text-app-faint",
};

export default function SectionLabel({
  children,
  tone = "faint",
  className,
  as = "div",
}: SectionLabelProps) {
  const Tag = as;

  return (
    <Tag
      className={cn(
        "font-mono text-[10px] uppercase tracking-[0.25em]",
        TONE_CLASS[tone],
        className,
      )}
    >
      {children}
    </Tag>
  );
}
