# ERP Conversacional con LLM

Proyecto base para una práctica universitaria orientada a un ERP conversacional. El sistema permite gestionar productos, proveedores, pedidos de compra, desechos y estadísticas desde una interfaz tipo chat, donde el usuario escribe instrucciones en lenguaje natural y un agente LLM interpreta la intención.

## 1. Descripción del proyecto

Este prototipo demuestra cómo integrar un backend ERP con un agente conversacional para reemplazar la navegación tradicional por una experiencia centrada en lenguaje natural. El usuario conversa con el sistema y el agente decide qué operación ejecutar sobre la API.

El proyecto está preparado para:

- CRUD de productos.
- CRUD de proveedores.
- CRUD de pedidos a proveedor.
- CRUD de desechos por caducidad o pérdida de stock.
- Consultas estadísticas.
- Comparación de proveedores LLM con arquitectura intercambiable.

## 2. Tecnologías utilizadas

- Python 3.12
- Django
- Django REST Framework
- MongoDB
- MongoEngine
- React
- Vite
- Docker
- Docker Compose

## 3. Arquitectura general

El repositorio se divide en tres servicios:

- `frontend`: cliente React con interfaz tipo chat.
- `backend`: API Django REST y agente conversacional.
- `mongodb`: base de datos persistente.

Flujo principal:

1. El usuario escribe un mensaje en el frontend.
2. El frontend llama a `POST /api/agent/chat/`.
3. El módulo `llm_agent` interpreta la intención con el proveedor configurado.
4. El backend ejecuta la operación correspondiente sobre MongoDB.
5. La respuesta devuelve texto, acción ejecutada y datos para renderizar tablas o gráficos.

## 4. Requisitos

Solo necesitas tener instalado:

- Docker
- Docker Compose

No es necesario instalar manualmente Python, Node.js ni MongoDB si ejecutas el proyecto con contenedores.

## 5. Cómo ejecutar en local con Docker

Desde la raíz del proyecto:

```bash
docker compose up --build
```

La primera ejecución descargará imágenes e instalará dependencias dentro de los contenedores.

También se incluyen scripts opcionales:

- Windows PowerShell: `./scripts/dev-up.ps1`
- Linux/macOS: `sh ./scripts/dev-up.sh`

## 6. URLs del sistema

- Frontend: [http://localhost:5173](http://localhost:5173)
- Backend API: [http://localhost:8000](http://localhost:8000)
- MongoDB: `localhost:27017`

Endpoints útiles:

- `GET /api/products/`
- `GET /api/suppliers/`
- `GET /api/purchase-orders/`
- `GET /api/waste/`
- `GET /api/statistics/overview/`
- `POST /api/agent/chat/`

## 7. Cómo probar el agente conversacional

1. Abre el frontend en `http://localhost:5173`.
2. Escribe una instrucción en el chat.
3. El frontend enviará el mensaje al backend.
4. La respuesta mostrará:
   - texto interpretado por el agente
   - acción ejecutada
   - datos asociados si aplica

También puedes probar por API:

```bash
curl -X POST http://localhost:8000/api/agent/chat/ \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"Muestrame todos los productos\",\"provider\":\"mock\"}"
```

## 8. Ejemplos de mensajes

- `Muéstrame todos los productos`
- `Crea un producto llamado Filtro HEPA con stock 20 y precio 35`
- `Registra un proveedor llamado ClimaSur con email contacto@climasur.com`
- `Crea un pedido al proveedor ClimaSur de 10 unidades de Filtro HEPA`
- `Registra un desecho de 3 unidades de Filtro HEPA por caducidad`
- `Muéstrame estadísticas de pérdidas por desechos`

## 9. Comparación de los 3 modelos LLM

La aplicación está preparada para comparar varios proveedores mediante una interfaz común:

```python
class BaseLLMProvider:
    def generate_response(self, user_message, context):
        pass
```

Implementaciones incluidas:

- `OpenAIProvider`
- `GeminiProvider`
- `LocalLLMProvider`
- `MockLLMProvider`

Notas:

- `MockLLMProvider` es el proveedor por defecto para pruebas locales.
- Los proveedores reales están preparados para integrarse sin cambiar el resto de la arquitectura.
- En el frontend puedes seleccionar el proveedor antes de enviar un mensaje.
- La respuesta del backend indica qué proveedor se ha utilizado.

## 10. Configuración opcional de claves API

El proyecto funciona sin claves gracias al `MockLLMProvider`, pero puedes preparar variables de entorno en `backend/.env.example`:

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `LOCAL_LLM_URL`
- `DEFAULT_LLM_PROVIDER`

Si configuras un proveedor real, puedes extender la lógica interna para llamar a su API sin romper la interfaz del agente.

## Estructura del proyecto

```text
erp-llm/
├── backend/
├── frontend/
├── docker-compose.yml
├── README.md
└── .gitignore
```

## Estado actual de esta base

La plantilla ya incluye:

- API REST funcional para entidades principales.
- Persistencia en MongoDB.
- Agente conversacional con parsing básico.
- Interfaz web de chat.
- Panel simple de estadísticas con tablas y gráficos básicos.
- Arranque unificado con Docker.

## Comando principal

```bash
docker compose up --build
```
