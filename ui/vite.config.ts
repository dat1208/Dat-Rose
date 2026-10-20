import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Tauri serves the dev UI on a fixed port and expects the build in dist/.
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    // Tauri's Rust build writes into src-tauri/target while Vite is running;
    // watching it makes Vite crash with EBUSY on locked build artifacts.
    watch: {
      ignored: ["**/src-tauri/**"],
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
