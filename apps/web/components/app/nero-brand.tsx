import Image from "next/image";
import Link from "next/link";

export default function NeroBrand({
  onClick,
  imgClassName = "h-auto w-full",
  sizes = "240px",
}: {
  onClick?: () => void;
  imgClassName?: string;
  sizes?: string;
}) {
  return (
    <Link href="/" onClick={onClick} className="app-focus-ring block">
      <Image
        src="/brand/nero-mascot-logo.png"
        alt="NERO — AI Job Intelligence"
        width={1312}
        height={1199}
        priority
        sizes={sizes}
        className={imgClassName}
      />
    </Link>
  );
}
