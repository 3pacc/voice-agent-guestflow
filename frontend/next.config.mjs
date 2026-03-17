/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: '/admin/live/:path*',
        destination: 'http://127.0.0.1:8000/admin/live/:path*',
      },
    ];
  },
};

export default nextConfig;
