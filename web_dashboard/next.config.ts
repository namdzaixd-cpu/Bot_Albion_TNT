import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Không lộ "X-Powered-By: Next.js" cho kẻ dò quét
  poweredByHeader: false,

  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          // Chặn nhúng trang vào iframe site khác (clickjacking)
          { key: "X-Frame-Options", value: "DENY" },
          // Không cho trình duyệt "đoán" kiểu file
          { key: "X-Content-Type-Options", value: "nosniff" },
          // Không rò URL dashboard sang site ngoài
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          // Tắt các quyền thiết bị không dùng tới
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
          // Ép HTTPS (Vercel đã có HTTPS sẵn)
          {
            key: "Strict-Transport-Security",
            value: "max-age=63072000; includeSubDomains; preload",
          },
        ],
      },
      {
        // API không được cache ở CDN/trình duyệt — tránh rò dữ liệu guild
        source: "/api/:path*",
        headers: [
          { key: "Cache-Control", value: "no-store, max-age=0" },
        ],
      },
    ];
  },
};

export default nextConfig;
