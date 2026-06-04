import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return;
          if (id.includes("/react/") || id.includes("/react-dom/") || id.includes("/scheduler/")) {
            return "react-vendor";
          }
          if (id.includes("/antd/")) {
            return "antd-vendor";
          }
          if (id.includes("/rc-") || id.includes("/@rc-component/")) {
            return "antd-support-vendor";
          }
          if (id.includes("/@ant-design/")) {
            return "antd-support-vendor";
          }
          if (id.includes("/echarts/") || id.includes("/zrender/")) {
            return "echarts-vendor";
          }
          if (id.includes("/react-router") || id.includes("/@remix-run/")) {
            return "router-vendor";
          }
          if (id.includes("/@tanstack/")) {
            return "query-vendor";
          }
          return "vendor";
        }
      }
    }
  },
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8070",
        changeOrigin: true
      }
    }
  }
});
