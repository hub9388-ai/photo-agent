import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone is only needed for the prepared Docker deployment.
  output: process.env.NEXT_PUBLIC_DEMO_MODE === "1" ? "export" : process.env.PHOTOAI_STANDALONE === "1" ? "standalone" : undefined,
  // Next 16 uses a custom distDir as the final export folder in export mode.
  distDir: process.env.NEXT_PUBLIC_DEMO_MODE === "1" ? "out-demo" : ".next",
  trailingSlash: process.env.NEXT_PUBLIC_DEMO_MODE === "1" ? true : undefined,
};

export default nextConfig;
