FROM node:20-alpine

WORKDIR /app

# Instala dependencias React/Vite antes de copiar el resto para aprovechar cache Docker.
COPY package.json ./
RUN npm install

# Copia el frontend completo; docker-compose monta tambien el volumen para desarrollo.
COPY . .

# Puerto de Vite usado por el navegador.
EXPOSE 5173

