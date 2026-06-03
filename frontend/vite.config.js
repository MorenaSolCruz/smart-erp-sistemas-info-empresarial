import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Configuracion de Vite para desarrollo: React se compila con el plugin oficial
// y el servidor escucha en 0.0.0.0 para que Docker pueda exponerlo al navegador.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
  },
});

