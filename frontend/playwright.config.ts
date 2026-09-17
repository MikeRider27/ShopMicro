import { defineConfig, devices } from "@playwright/test";

// Corre contra el stack completo ya desplegado (frontend + gateway + los 3
// microservicios) — no levanta nada por su cuenta. Ver README para cómo
// correrla.
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
