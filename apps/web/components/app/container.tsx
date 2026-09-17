import { cn } from "@/lib/utils";

type ContainerProps = {
  children: React.ReactNode;
  className?: string;
  /**
   * "default" is the standard content width shared by every app-shell
   * page (dashboard, jobs, resume). "narrow" is for single-column forms
   * (settings) where a shorter line length is more readable.
   */
  size?: "default" | "narrow";
};

const MAX_WIDTH = {
  default: "max-w-[1440px]",
  narrow: "max-w-[880px]",
};

export default function Container({
  children,
  className,
  size = "default",
}: ContainerProps) {
  return (
    <div
      className={cn(
        "mx-auto w-full px-5 py-8 md:px-8 lg:px-10 lg:py-12",
        MAX_WIDTH[size],
        className,
      )}
    >
      {children}
    </div>
  );
}
