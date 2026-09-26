import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * The landing page's single section-header pattern: mono eyebrow with
 * a crimson hairline, display heading, optional lede.
 *
 * Every section used to hand-roll this trio, which is why no two
 * headers shared an eyebrow size, a hairline length, a heading clamp,
 * or a heading-to-lede gap. Content is unchanged — only the spacing
 * and type steps are now shared (see .section-eyebrow /
 * .display-section / .section-lede in globals.css).
 */
export default function SectionHeading({
  eyebrow,
  title,
  lede,
  align = "left",
  size = "section",
  className,
  titleClassName,
  ledeClassName,
  children,
}: {
  eyebrow: ReactNode;
  title: ReactNode;
  lede?: ReactNode;
  align?: "left" | "center";
  size?: "section" | "sub";
  className?: string;
  titleClassName?: string;
  ledeClassName?: string;
  children?: ReactNode;
}) {
  const centered = align === "center";

  return (
    <div
      className={cn(
        centered ? "flex flex-col items-center text-center" : "flex flex-col",
        className,
      )}
    >
      <p
        className={cn(
          "section-eyebrow",
          centered && "section-eyebrow-center",
        )}
      >
        {eyebrow}
      </p>

      <h2
        className={cn(
          size === "sub" ? "display-sub" : "display-section",
          "mt-5",
          centered && "mx-auto",
          titleClassName,
        )}
      >
        {title}
      </h2>

      {lede ? (
        <p
          className={cn(
            "section-lede mt-5",
            centered && "mx-auto text-center",
            ledeClassName,
          )}
        >
          {lede}
        </p>
      ) : null}

      {children}
    </div>
  );
}
