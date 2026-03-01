import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "image.aladin.co.kr",
      },
      {
        protocol: "https",
        hostname: "covers.openlibrary.org",
      },
      {
        protocol: "http",
        hostname: "image.aladin.co.kr",
      },
      {
        protocol: "https",
        hostname: "*.aladin.co.kr",
      },
    ],
  },
};

export default nextConfig;
