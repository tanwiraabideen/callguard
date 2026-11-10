import type { NextConfig } from "next";

// The site is one browser-only page, so it builds to plain files in out/.
const nextConfig: NextConfig = {
  output: "export",
};

export default nextConfig;
