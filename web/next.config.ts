import type { NextConfig } from '@/next'
import createMDX from '@next/mdx'
import { codeInspectorPlugin } from 'code-inspector-plugin'
import type { Configuration } from 'webpack'
import { env } from './env'

const isDev = process.env.NODE_ENV === 'development'
const withMDX = createMDX()

const nextConfig: NextConfig = {
  basePath: env.NEXT_PUBLIC_BASE_PATH,
  transpilePackages: ['@t3-oss/env-core', '@t3-oss/env-nextjs'],
  turbopack: {
    root: process.cwd(),
    // 仅在非开发模式启用 codeInspectorPlugin（开发模式下禁用以减少内存占用）
    ...(isDev
      ? {}
      : {
          rules: codeInspectorPlugin({
            bundler: 'turbopack',
          }),
        }),
  },
  productionBrowserSourceMaps: false, // enable browser source map generation during the production build
  // Configure pageExtensions to include md and mdx
  pageExtensions: ['ts', 'tsx', 'js', 'jsx', 'md', 'mdx'],
  typescript: {
    // https://nextjs.org/docs/api-reference/next.config.js/ignoring-typescript-errors
    ignoreBuildErrors: true,
  },
  async redirects() {
    return [
      {
        source: '/',
        destination: '/apps',
        permanent: false,
      },
    ]
  },
  output: 'standalone',
  compiler: {
    removeConsole: isDev ? false : { exclude: ['warn', 'error'] },
  },
  // 修复 Windows 盘符大小写不一致导致模块重复加载的问题
  webpack: (config: Configuration) => {
    if (!config.resolve) config.resolve = {}
    // 禁用带 context 的缓存键，避免同一模块因路径大小写不同被缓存为两个实例
    ;(config.resolve as Record<string, unknown>).cacheWithContext = false
    return config
  },
  // 移除实验性 Turbopack 文件系统缓存（减少内存占用）
}

export default withMDX(nextConfig)
