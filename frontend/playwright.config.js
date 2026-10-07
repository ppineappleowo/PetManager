import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  testMatch: '**/*.spec.js',
  fullyParallel: true,
  use: { baseURL: 'http://127.0.0.1:5501', browserName: 'chromium', channel: process.env.PLAYWRIGHT_CHANNEL || undefined, trace: 'retain-on-failure' },
  webServer: {
    command: 'npm run dev -- --port 5501',
    url: 'http://127.0.0.1:5501',
    reuseExistingServer: false,
    timeout: 30000,
  },
})
