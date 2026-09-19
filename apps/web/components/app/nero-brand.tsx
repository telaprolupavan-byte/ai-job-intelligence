import Image from "next/image";
import Link from "next/link";

export default function NeroBrand({ onClick }: { onClick?: () => void }) {
  return (
    <Link href="/" onClick={onClick} className="app-focus-ring block">
      <Image
        src="/brand/nero-mascot-logo.png"
        alt="NERO — AI Job Intelligence"
        width={1312}
        height={1199}
        priority
        sizes="240px"
        className="h-auto w-full"
      />
    </Link>
  );
}
