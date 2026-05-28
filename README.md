# ERP Conversacional con LLM

Prototipo de ERP conversacional orientado a una practica universitaria de Sistemas de la Informacion Empresarial. Toda la interaccion con el sistema se realiza por lenguaje natural desde un chat: el usuario no navega por menus tradicionales, sino que pide acciones al asistente y este decide que operacion ejecutar sobre el backend.

## 1. Objetivo

El proyecto implementa un ERP conversacional con:

- gestion de productos
- gestion de proveedores
- gestion de pedidos a proveedor
- gestion de desechos
- consultas estadisticas
- memoria operativa del chat
- auditoria y trazabilidad consultable por prompt
- soporte para varios proveedores LLM

## 2. Stack tecnologico

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

- `frontend`: cliente React con interfaz tipo chat
- `backend`: API Django REST y agente conversacional
- `mongodb`: base de datos persistente

Flujo principal:

1. El usuario escribe un mensaje en el frontend.
2. El frontend llama a `POST /api/agent/chat/`.
3. El modulo `llm_agent` interpreta la intencion.
4. El backend ejecuta la operacion correspondiente sobre MongoDB.
5. La respuesta devuelve texto, accion ejecutada y datos para renderizar tablas o graficos.

## 4. Requisitos

Solo necesitas tener instalado:

- Docker
- Docker Compose

No hace falta instalar manualmente Python, Node.js ni MongoDB si ejecutas el proyecto con contenedores.

## 5. Configuracion inicial

Antes del primer arranque hay que crear el archivo `backend/.env` a partir del ejemplo:

```powershell
Copy-Item .\backend\.env.example .\backend\.env
```

Alternativa:

```powershell
cp .\backend\.env.example .\backend\.env
```

## 6. Como ejecutar en local con Docker

Desde la raiz del proyecto:

```bash
docker compose up --build
```

Tambien se incluyen scripts opcionales:

- Windows PowerShell: `./scripts/dev-up.ps1`
- Linux/macOS: `sh ./scripts/dev-up.sh`

En el arranque del backend se ejecuta automaticamente:

1. espera a MongoDB
2. carga datos demo si la base esta vacia
3. levanta el servidor Django

## 7. URLs del sistema

- Frontend: [http://localhost:5173](http://localhost:5173)
- Backend API: [http://localhost:8000](http://localhost:8000)
- MongoDB: `localhost:27017`

Endpoints utiles:

- `GET /api/products/`
- `GET /api/suppliers/`
- `GET /api/purchase-orders/`
- `GET /api/waste/`
- `GET /api/statistics/overview/`
- `POST /api/agent/chat/`

## 8. Proveedores LLM y claves API

No, no es obligatorio configurar un token para que el proyecto funcione. Por defecto usa `mock`, asi que se puede probar sin claves reales.

Las claves se configuran en:

- [backend/.env](C:\Users\moren\Documents\Repositorios\smart-erp-sistemas-info-empresarial\backend\.env)

Variables disponibles:

- `DEFAULT_LLM_PROVIDER=mock`
- `OPENAI_API_KEY=`
- `OPENAI_MODEL=gpt-4o-mini`
- `GEMINI_API_KEY=`
- `GEMINI_MODEL=gemini-2.5-flash`
- `ANTHROPIC_API_KEY=`
- `ANTHROPIC_MODEL=claude-3-5-haiku-latest`
- `LOCAL_LLM_URL=http://localhost:11434`

Ejemplos:

- para usar OpenAI:

```env
DEFAULT_LLM_PROVIDER=openai
OPENAI_API_KEY=tu_clave_aqui
OPENAI_MODEL=gpt-4o-mini
```

- para usar Gemini:

```env
DEFAULT_LLM_PROVIDER=gemini
GEMINI_API_KEY=tu_clave_aqui
GEMINI_MODEL=gemini-2.5-flash
```

- para usar Claude:

```env
DEFAULT_LLM_PROVIDER=claude
ANTHROPIC_API_KEY=tu_clave_aqui
ANTHROPIC_MODEL=claude-3-5-haiku-latest
```

Si no configuras ninguna clave, el sistema seguira funcionando con `mock`.

## 9. Funcionalidades implementadas

### CRUD principal

- productos
- proveedores
- pedidos a proveedor
- desechos

### Estadisticas

El panel incluye, entre otras:

- productos con stock bajo
- productos mas desechados
- perdidas economicas por motivo
- pedidos por proveedor
- resumen de caducidad automatica

### Caducidad automatica

Si un producto tiene `expiration_date` vencida y stock disponible:

- el sistema lo detecta automaticamente
- descuenta el stock
- genera un registro de desecho con motivo `caducidad`
- calcula la perdida economica

### Memoria operativa del chat

El asistente recuerda contexto reciente para hacer el dialogo mas natural.

Ejemplo:

1. `Registra un proveedor llamado TecnoSur con email compras@tecnosur.com`
2. `Hazle un pedido de 10 unidades de Filtro HEPA`

En el segundo mensaje ya no hace falta repetir el proveedor.

### Confirmaciones inteligentes

El chat pide confirmacion antes de acciones masivas o especialmente destructivas como:

- vaciar inventario
- borrar todos los proveedores
- eliminar todos los desechos registrados

Las operaciones sobre registros concretos, como eliminar un proveedor, borrar un pedido o eliminar un producto especifico, se ejecutan directamente por conversacion. Esto mantiene la demo mas fluida y evita pasos innecesarios cuando el usuario ya ha indicado claramente el registro que quiere modificar.

### Sugerencias proactivas

Si una operacion deja un producto por debajo del stock minimo, el sistema avisa en la respuesta.

Ejemplo:

- `Este producto ha quedado por debajo del stock minimo. Quieres generar un pedido?`

### Reposicion automatica configurable

Por defecto esta desactivada.

Se puede activar o desactivar por prompt:

- `Activa la reposicion automatica`
- `Desactiva la reposicion automatica`

Cuando esta activa, si una operacion deja un producto por debajo del stock minimo, el backend intenta generar automaticamente un pedido al proveedor asociado a ese producto.

### Auditoria y trazabilidad por prompt

No hay botones especificos para ello: se consulta desde el propio chat.

Ejemplos:

- `Muestrame las ultimas 10 acciones sobre este proveedor`
- `Muestrame las ultimas 10 acciones sobre el proveedor TecnoSur`
- `Dime cuales son los ultimos 35 productos eliminados`

Si el usuario pide mas registros de los que existen, el sistema responde de forma parcial y lo explica. Por ejemplo, si pide 35 y solo hay 10, indicara que solo existen 10 y mostrara esos 10.

### Datos demo automáticos

Si la base de datos esta vacia, el backend carga automaticamente:

- proveedores demo
- productos demo
- pedidos demo
- desechos demo

Esto permite hacer una demo fuerte desde el primer minuto sin preparar datos a mano.

## 10. Como probar el agente conversacional

1. Abre el frontend en [http://localhost:5173](http://localhost:5173).
2. Escribe instrucciones en el chat.
3. Revisa la respuesta textual y el panel lateral.

Tambien puedes probar por API:

```bash
curl -X POST http://localhost:8000/api/agent/chat/ \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"Muestrame todos los productos\",\"provider\":\"mock\"}"
```

## 11. Prompts recomendados para la demo

### Demo basica

- `Muestrame todos los productos`
- `Muestrame todos los proveedores`
- `Muestrame estadisticas`

### CRUD

- `Crea un producto llamado Filtro HEPA con stock 20 y precio 35`
- `Registra un proveedor llamado ClimaSur con email contacto@climasur.com`
- `Crea un pedido al proveedor ClimaSur de 10 unidades de Filtro HEPA`
- `Registra un desecho de 3 unidades de Filtro HEPA por caducidad`
- `Elimina el proveedor ClimaSur`
- `Elimina pedido <id corto>`
- `Elimina producto Filtro HEPA`

### Memoria operativa

- `Registra un proveedor llamado TecnoSur con email compras@tecnosur.com`
- `Hazle un pedido de 10 unidades de Sensor Termico`

### Confirmaciones inteligentes

- `Borra todos los proveedores`
- responde `si` o `no`

- `Elimina todo el inventario`
- responde `si` o `no`

- `Elimina todos los desechos registrados`
- responde `si` o `no`

### Consultas avanzadas

- `Muestrame los productos con menos de 5 unidades`
- `Que producto tiene mas stock?`
- `Ordena los productos por precio descendente`
- `Busca productos cuyo nombre contenga sensor`
- `Cuanto vale el inventario total?`
- `Dame los 10 productos mas caros`
- `Que proveedor tiene mas pedidos?`
- `Dame un resumen del inventario actual`

### Automatizaciones

- `Activa reposicion automatica para productos con menos de 5 unidades`
- `Desactiva las alertas automaticas de stock`
- `Genera automaticamente pedidos cuando un producto se quede sin stock`

### Reposicion automatica

- `Activa la reposicion automatica`
- `Consulta el stock de Sensor Termico`
- `Desactiva la reposicion automatica`

### Trazabilidad

- `Muestrame las ultimas 10 acciones sobre este proveedor`
- `Dime cuales son los ultimos 35 productos eliminados`

## 12. Notas para la demo con datos demo

El seed demo solo se ejecuta si MongoDB esta vacia.

Si ya habias arrancado antes y quieres volver a una demo limpia, puedes borrar el volumen de Mongo y volver a levantar:

```bash
docker compose down -v
docker compose up --build
```

Atencion: `docker compose down -v` elimina los datos persistidos de MongoDB de esta demo local.

## 13. Estructura del proyecto

```text
smart-erp-sistemas-info-empresarial/
├── backend/
├── frontend/
├── docker-compose.yml
├── README.md
└── .gitignore
```

## 14. Estado actual

La base ya incluye:

- API REST funcional para entidades principales
- persistencia en MongoDB
- agente conversacional con memoria operativa
- caducidad automatica
- confirmaciones inteligentes
- sugerencias proactivas
- reposicion automatica configurable
- auditoria y trazabilidad por prompt
- interfaz web de chat
- dashboard estadistico
- carga automatica de datos demo
- arranque unificado con Docker

## 15. Comando principal

```bash
docker compose up --build
```
