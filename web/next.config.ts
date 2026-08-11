import type { Configuration } from 'webpack'
import type { NextConfig } from '@/next'
import createMDX from '@next/mdx'
import { codeInspectorPlugin } from 'code-inspector-plugin'
import { env } from './env'

const isDev = process.env.NODE_ENV === 'development'
const withMDX = createMDX()

const nextConfig: NextConfig = {
  basePath: env.NEXT_PUBLIC_BASE_PATH,
  transpilePackages: ['@t3-oss/env-core', '@t3-oss/env-nextjs'],
  allowedDevOrigins: ['127.0.0.1'],
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
  // 修复 Windows 盘符大小写不一致导致 React 被加载为两个实例的问题
  webpack: (config: Configuration) => {
    if (!config.resolve)
      config.resolve = {}
    if (!config.resolve.plugins)
      config.resolve.plugins = []

    // 抑制 ESM/CJS 互操作警告（decode-named-character-reference, parse-entities 等）
    // 这些警告来自 react-syntax-highlighter 的依赖链，不影响功能
    config.ignoreWarnings = [
      ...(config.ignoreWarnings || []),
      {
        message: /Can't import the named export/,
      },
      {
        message: /only default export is available/,
      },
      {
        message: /Attempted import error/,
      },
      {
        message: /is not exported from/,
      },
    ]

    // 禁用 webpack 严格导出检查，防止 ESM/CJS 互操作的缺失导出变为致命错误
    // （d3-contour 引用 d3-array 的 blur2、mermaid 引用 d3 的 curveBumpX 等）
    if (config.module) {
      config.module.strictExportPresence = false
      config.module.strictThisContextOnImports = false
    }

    // 核心修复：在模块解析完成后统一 Windows 盘符为大写，
    // 防止同一模块因 E:\ vs e:\ 路径差异被 webpack 识别为两个不同模块
    config.resolve.plugins.push({
      // eslint-disable-next-line ts/no-explicit-any
      apply(resolver: any) {
        // eslint-disable-next-line ts/no-explicit-any
        resolver.hooks.resolved.tap('NormalizeDriveCase', (request: any) => {
          if (request.path && /^[a-z]:\\/i.test(request.path)) {
            request.path = request.path[0].toUpperCase() + request.path.slice(1)
          }
        })
      },
    })

    return config
  },
  // 移除实验性 Turbopack 文件系统缓存（减少内存占用）
}

export default withMDX(nextConfig)
