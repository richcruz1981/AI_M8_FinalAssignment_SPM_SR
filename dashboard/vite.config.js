import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base "./": the site lives under /iaang01/edgarcruz/ — relative asset paths work at any depth.
export default defineConfig({ plugins: [react()], base: "./", build: { outDir: "dist", sourcemap: false } });
