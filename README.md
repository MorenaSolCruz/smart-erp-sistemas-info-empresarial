# ERP Conversacional con LLM

Prototipo de ERP conversacional desarrollado para una practica universitaria de Sistemas de la Informacion Empresarial. Toda la interaccion principal se realiza desde un chat: el usuario escribe instrucciones en lenguaje natural y el backend interpreta la intencion para ejecutar operaciones sobre inventario, proveedores, pedidos, desechos y estadisticas.

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
- Django 5
- Django REST Framework
- MongoDB
- MongoEngine
- React 18
- Vite 5
- Docker
- Docker Compose

## 3. Arquitectura general

El repositorio se organiza en tres piezas:

- `frontend`: cliente React con interfaz tipo chat y panel lateral de datos
- `backend`: API Django REST, logica de negocio y agente conversacional
- `mongodb`: persistencia de datos

Flujo principal:

1. El usuario escribe un mensaje en el frontend.
2. El frontend envia la peticion a `POST /api/agent/chat/`.
3. El modulo `llm_agent` clasifica la intencion.
4. El backend ejecuta la operacion correspondiente sobre MongoDB.
5. La respuesta devuelve texto, accion ejecutada y datos para el panel.

## 4. Requisitos

Para ejecutar el proyecto en local solo hace falta:

- Docker
- Docker Compose

No es necesario instalar Python, Node.js ni MongoDB manualmente si se usa la ejecucion con contenedores.

## 5. Configuracion inicial

Antes del primer arranque crea el archivo `backend/.env` a partir del ejemplo:

```powershell
Copy-Item .\backend\.env.example .\backend\.env
```

El frontend ya dispone de `frontend/.env.example`. Si quieres un archivo local explicito, puedes copiarlo tambien:

```powershell
Copy-Item .\frontend\.env.example .\frontend\.env
```

## 6. Como ejecutar en local con Docker

Desde la raiz del proyecto:

```bash
docker compose up --build
```

Tambien existen scripts de apoyo:

- Windows PowerShell: `./scripts/dev-up.ps1`
- Linux/macOS: `sh ./scripts/dev-up.sh`

En el arranque del backend se hace automaticamente:

1. espera a MongoDB
2. carga datos demo si la base esta vacia
3. levanta Django en `0.0.0.0:8000`

## 7. URLs y endpoints

URLs locales:

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
- `GET /api/agent/metrics/`

## 8. Variables de entorno

### Backend

Archivo: `backend/.env`

Variables disponibles:

```env
DJANGO_SECRET_KEY=django-insecure-change-me
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,backend
MONGODB_URI=mongodb://mongodb:27017/erp_llm
MONGODB_DB_NAME=erp_llm
DEFAULT_LLM_PROVIDER=mock
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-3-5-haiku-latest
LOCAL_LLM_URL=http://localhost:11434
LOCAL_LLM_MODEL=llama3.1:8b
```

### Frontend

Archivo opcional: `frontend/.env`

```env
VITE_API_BASE_URL=http://localhost:8000/api
VITE_DEFAULT_LLM_PROVIDER=mock
```

## 9. Proveedores LLM soportados

El proyecto puede funcionar sin claves externas usando `mock`, que es la opcion mas comoda para una demo o una entrega academica.

Proveedores soportados:

- `mock`
- `openai`
- `gemini`
- `gemini-2.5-flash`
- `gemini-2.5-flash-lite`
- `gemini-2.0-flash`
- `claude`

Notas:

- el alias `gemini` usa internamente `gemini-2.5-flash`
- el selector del frontend permite cambiar el proveedor en caliente
- si no configuras claves API, el sistema sigue siendo usable con `mock`

Ejemplo para Gemini:

```env
DEFAULT_LLM_PROVIDER=gemini
GEMINI_API_KEY=tu_clave_aqui
GEMINI_MODEL=gemini-2.5-flash
```

## 10. Funcionalidades implementadas

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

El asistente recuerda contexto reciente para permitir conversaciones mas naturales.

Ejemplo:

1. `Registra un proveedor llamado TecnoSur con email compras@tecnosur.com`
2. `Hazle un pedido de 10 unidades de Filtro HEPA`

En el segundo mensaje ya no hace falta repetir el proveedor.

### Confirmaciones inteligentes

El chat pide confirmacion antes de acciones masivas o especialmente destructivas como:

- `Elimina todo el inventario`
- `Borra todos los proveedores`
- `Elimina los pedidos`
- `Elimina todos los desechos registrados`

Las operaciones sobre registros concretos, como eliminar un proveedor concreto o borrar un pedido concreto, siguen siendo directas para mantener la demo fluida.

### Sugerencias proactivas

Si una operacion deja un producto por debajo del stock minimo, el sistema lo indica en la respuesta.

Ejemplo:

- `Este producto ha quedado por debajo del stock minimo. Quieres generar un pedido?`

### Reposicion automatica configurable

Por defecto esta desactivada.

Se puede activar o desactivar por prompt:

- `Activa la reposicion automatica`
- `Desactiva la reposicion automatica`
- `Genera automaticamente pedidos cuando un producto se quede sin stock`

Cuando esta activa, si una operacion deja un producto por debajo del umbral configurado, el backend intenta crear un pedido automaticamente para el proveedor asociado.

### Auditoria y trazabilidad por prompt

No hay una pantalla separada para esto: se consulta desde el propio chat.

Ejemplos:

- `Muestrame las ultimas 10 acciones sobre este proveedor`
- `Muestrame las ultimas 10 acciones sobre el proveedor TecnoSur`
- `Dime cuales son los ultimos 35 productos eliminados`

## 11. Datos demo

Si la base de datos esta vacia, el backend carga automaticamente un seed demo al arrancar.

Estado demo esperado:

- 5 productos: `Filtro HEPA`, `Sensor Termico`, `Valvula Industrial`, `Guante Nitrilo`, `Kit Analitico`
- 3 proveedores: `TecnoSur`, `ClimaPro`, `NovaLab`
- 2 pedidos demo
- 2 desechos demo

Nota importante:

- aunque el seed crea inicialmente 1 desecho manual, el propio sistema procesa productos caducados al arrancar y deja finalmente 2 desechos en el estado demo normal

## 12. Como volver al estado demo inicial

La forma mas sencilla es vaciar la persistencia de MongoDB y volver a levantar el proyecto:

```bash
docker compose down -v
docker compose up --build
```

Atencion:

- `docker compose down -v` elimina los datos persistidos de MongoDB de esta demo local

## 13. Como probar el agente conversacional

1. Abre el frontend en [http://localhost:5173](http://localhost:5173).
2. Escribe instrucciones en el chat.
3. Revisa la respuesta textual y el panel lateral.

Tambien se puede probar por API:

```bash
curl -X POST http://localhost:8000/api/agent/chat/ \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"Muestrame todos los productos\",\"provider\":\"mock\"}"
```

## 14. Prompts recomendados para la demo

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
- `Elimina pedido <id>`
- `Elimina producto Filtro HEPA`

### Memoria operativa

- `Registra un proveedor llamado TecnoSur con email compras@tecnosur.com`
- `Hazle un pedido de 10 unidades de Sensor Termico`

### Confirmaciones inteligentes

- `Borra todos los proveedores`
- responde `si` o `no`

- `Elimina todo el inventario`
- responde `si` o `no`

- `Elimina los pedidos`
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

### Trazabilidad

- `Muestrame las ultimas 10 acciones sobre este proveedor`
- `Dime cuales son los ultimos 35 productos eliminados`

## 15. Estructura del proyecto

```text
smart-erp-sistemas-info-empresarial/
|-- backend/
|-- frontend/
|-- scripts/
|-- docker-compose.yml
|-- README.md
`-- .gitignore
```

## 16. Notas para entrega

Si el proyecto se va a entregar comprimido en `.zip`, lo recomendable es incluir:

- codigo fuente completo
- `README.md`
- `docker-compose.yml`
- `backend/.env.example`
- `frontend/.env.example`

Conviene no incluir:

- `.git/`
- `frontend/node_modules/`
- `frontend/dist/`
- `mongodb_data/`
- `__pycache__/`
- caches de pruebas o de herramientas

Tampoco conviene compartir `backend/.env` si contiene claves reales.

## 17. Comando principal

```bash
docker compose up --build
```
