import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["192.168.0.119"],
  turbopack: {
    root: "/home/mrcaro/Projects/3D Avatar RAG",
  },
};

export default nextConfig;