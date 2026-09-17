import Link from "next/link";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "default" | "sm" | "icon";

const VARIANT_CLASS: Record<Variant, string> = {
  // bg-crimson-fill (not bg-app-red) — a deepened shade so the white
  // label clears WCAG AA contrast; see globals.css for the rationale.
  primary:
    "bg-crimson-fill text-white hover:bg-crimson-fill-hover hover:shadow-[0_0_20px_rgba(255,59,48,0.3)] focus-visible:ring-app-red/40",
  secondary:
    "border border-app-border-strong text-app-text hover:border-app-blue hover:text-white focus-visible:ring-app-blue/40",
  ghost:
    "border border-app-border text-app-muted hover:border-app-border-strong hover:text-app-text focus-visible:ring-app-blue/40",
  danger:
    "border border-app-red/50 bg-app-red/10 text-app-red hover:bg-app-red/20 focus-visible:ring-app-red/40",
};

const SIZE_CLASS: Record<Size, string> = {
  default: "h-11 gap-2 px-5 text-xs",
  sm: "h-9 gap-1.5 px-4 text-[11px]",
  icon: "h-10 w-10 shrink-0",
};

const BASE_CLASS =
  "inline-flex items-center justify-center whitespace-nowrap rounded-lg font-bold uppercase tracking-[0.1em] transition-colors outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-app-bg disabled:cursor-not-allowed disabled:opacity-50";

type CommonProps = {
  variant?: Variant;
  size?: Size;
  className?: string;
  loading?: boolean;
  children: React.ReactNode;
};

type ButtonAsButton = CommonProps &
  React.ButtonHTMLAttributes<HTMLButtonElement> & { href?: undefined };

type ButtonAsLink = CommonProps & {
  href: string;
  target?: string;
  rel?: string;
};

export default function AppButton(props: ButtonAsButton | ButtonAsLink) {
  const {
    variant = "primary",
    size = "default",
    className,
    loading = false,
    children,
    ...rest
  } = props;

  const classes = cn(
    BASE_CLASS,
    VARIANT_CLASS[variant],
    SIZE_CLASS[size],
    className,
  );

  if ("href" in props && props.href) {
    const { href, target, rel } = props;

    // External links (anything opened in a new tab) use a plain anchor;
    // next/link's client-side routing is only meaningful for same-origin
    // navigation.
    if (target) {
      return (
        <a href={href} target={target} rel={rel} className={classes}>
          {children}
        </a>
      );
    }

    return (
      <Link href={href} className={classes}>
        {children}
      </Link>
    );
  }

  const buttonProps = rest as React.ButtonHTMLAttributes<HTMLButtonElement>;

  return (
    <button
      type="button"
      {...buttonProps}
      disabled={buttonProps.disabled || loading}
      className={classes}
    >
      {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
      {children}
    </button>
  );
}
