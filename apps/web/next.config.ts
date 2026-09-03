import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@sentinel/shared"],
  // Proxy all /api/* traffic to the FastAPI backend. The browser only ever
  // talks to the Next origin, which keeps the refresh-token cookie
  // SameSite=Lax friendly and enables middleware-style gating later.
  async rewrites() {
    const backend = process.env.API_BACKEND_URL ?? "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backend}/api/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/api/:path*",
        headers: [
          { key: "Cache-Control", value: "no-store" },
          { key: "X-Content-Type-Options", value: "nosniff" },
        ],
      },
    ];
  },
};

export default nextConfig;