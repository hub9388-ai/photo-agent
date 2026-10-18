import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone is only needed for the prepared Docker deployment.
  output: process.env.PHOTOAI_STANDALONE === "1" ? "standalone" : undefined,
};

export default nextConfig;
