import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    // Next.js 16 restricts `quality` to this allowlist (defaults to [75]
    // otherwise). The brand mark has fine gradients/highlights that show
    // visible softening at 75, so a higher tier is added for it.
    qualities: [75, 95],
  },
};

export default nextConfig;
