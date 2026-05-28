import os
import json
import re
import unicodedata

import requests


ALLOWED_INTENTS = {
    "help",
    "confirmation_required",
    "missing_data",
    "fallback",
    "list_products",
    "create_product",
    "add_product_stock",
    "update_product",
    "delete_product",
    "delete_all_products",
    "query_products",
    "get_product_stock",
    "list_suppliers",
    "create_supplier",
    "update_supplier",
    "delete_supplier",
    "delete_all_suppliers",
    "list_purchase_orders",
    "create_purchase_order",
    "update_purchase_order",
    "delete_purchase_order",
    "query_purchase_orders",
    "complete_purchase_order",
    "cancel_latest_purchase_order",
    "list_waste",
    "create_waste",
    "update_waste",
    "delete_waste",
    "delete_all_waste",
    "show_statistics",
    "show_audit_history",
    "configure_auto_replenishment",
}


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": sorted(ALLOWED_INTENTS),
            "description": "Accion ERP que debe ejecutar el backend.",
        },
        "reply": {
            "type": "string",
            "description": "Respuesta breve en espanol para el usuario.",
        },
        "data": {
            "type": "object",
            "description": "Datos necesarios para ejecutar la accion. Usar objeto vacio si no aplica.",
            "additionalProperties": True,
        },
    },
    "required": ["intent", "reply", "data"],
    "additionalProperties": False,
}

CONFIRMATION_PREFIX = "confirm_action::"


SYSTEM_PROMPT = """
Eres Maja, el clasificador de intenciones de un prototipo ERP conversacional.
Tu unica salida debe ser JSON valido con esta forma:
{"intent": "...", "reply": "...", "data": {...}}

No ejecutes operaciones por tu cuenta. Solo interpreta el mensaje del usuario.
El backend ejecutara la operacion indicada.
Tu trabajo es entender lenguaje natural aunque el usuario escriba con faltas,
sin tildes, con palabras incompletas o en orden distinto.

Intenciones permitidas:
- help
- confirmation_required
- missing_data
- fallback
- list_products, create_product, add_product_stock, update_product, delete_product, delete_all_products
- query_products para filtros, ordenaciones y analitica de inventario
- get_product_stock para preguntas como "cuantos monitores tengo" o "stock de Filtro HEPA"
- list_suppliers, create_supplier, update_supplier, delete_supplier
- list_purchase_orders, create_purchase_order, update_purchase_order, delete_purchase_order, query_purchase_orders
- complete_purchase_order y cancel_latest_purchase_order
- list_waste, create_waste, update_waste, delete_waste, delete_all_waste
- show_statistics
- show_audit_history para trazabilidad y auditoria
- configure_auto_replenishment para activar o desactivar la reposicion automatica

Reglas de seguridad:
- Para eliminar un producto, proveedor, pedido o desecho concreto, usa delete_* directamente.
- Solo pide confirmation_required si el usuario quiere eliminar todo el inventario, todos los proveedores,
  todos los desechos o todos los registros de una entidad.
- Si faltan campos obligatorios, usa missing_data.
- Si la intencion no es clara, usa fallback.
- Si el usuario pregunta que puedes hacer, ejemplos, ayuda, comandos o capacidades, usa help.
- Si pregunta "que productos tengo", "que hay en inventario", "objetos en stock", usa list_products.
- Si pregunta "cuantos monitores tengo", "stock de tablets", "cantidad de telefono", usa get_product_stock.
- Si dice "agrega", "añade", "mete", "introduce", "registra" un producto con unidades/precio,
  interpreta create_product o add_product_stock segun corresponda.
- Si da precio y unidades para un producto nuevo, usa create_product.
- Si solo da unidades para un producto, usa add_product_stock.

Campos esperados por intencion:
- create_product: data.name, data.stock, data.unit_price. Opcionales: description, category, minimum_stock.
- add_product_stock: data.name, data.quantity. Si el producto no existe, el backend puede crearlo con precio 0.
- update_product: data.name y al menos uno de new_name, stock, unit_price, category, minimum_stock.
- delete_product: data.name.
- delete_all_products: data debe ser {}.
- query_products: data.kind y opcionalmente data.limit, data.threshold, data.search.
- get_product_stock: data.name.
- create_supplier: data.name, data.contact_email. Opcionales: phone, address, products_supplied.
- update_supplier: data.name y al menos uno de new_name, contact_email, phone, address.
- delete_supplier: data.name.
- delete_all_suppliers: data debe ser {}.
- create_purchase_order: data.supplier_name, data.items. Cada item necesita product_name y quantity. unit_price opcional.
- update_purchase_order: data.id, data.supplier_name, data.items. status opcional.
- delete_purchase_order: data.id.
- query_purchase_orders: data.kind.
- complete_purchase_order: data.id.
- cancel_latest_purchase_order: data debe ser {}.
- create_waste: data.product_name, data.quantity, data.reason. reason debe ser caducidad, producto dañado o ajuste manual.
- update_waste: data.id, data.product_name, data.quantity, data.reason.
- delete_waste: data.id.
- delete_all_waste: data debe ser {}.
- show_audit_history: data.audit_scope, data.limit y segun el caso data.supplier_name.
- configure_auto_replenishment: data.enabled con valor true o false.
- list_* y show_statistics: data debe ser {}.

Normaliza nombres propios de productos y proveedores con mayusculas profesionales.
Responde siempre en espanol profesional y breve.

Ejemplos de interpretacion:
- "agrega televisor con precio 300 y 5 unidades" -> create_product con name Televisor, stock 5, unit_price 300.
- "mete 10 ratones al inventario" -> add_product_stock con name Ratones, quantity 10.
- "cuantos monitores tengo?" -> get_product_stock con name Monitores.
- "que hay en el inventario?" -> list_products.
- "quiero ver proveedores" -> list_suppliers.
- "haz un pedido a ClimaSur de 8 filtros HEPA" -> create_purchase_order.
- "borra el producto Tablet" -> delete_product.
- "elimina telefono" -> delete_product con name Telefono.
- "elimina todo el inventario" -> confirmation_required con data.pending_action delete_all_products.
- "confirma eliminar todo el inventario" -> delete_all_products.
- "muestrame las ultimas 10 acciones sobre este proveedor" -> show_audit_history.
- "dime los ultimos 35 productos eliminados" -> show_audit_history.
""".strip()


class BaseLLMProvider:
    name = "base"

    def generate_response(self, user_message, context):
        raise NotImplementedError


def normalize_text(value):
    value = unicodedata.normalize("NFD", value.strip().lower())
    return "".join(char for char in value if unicodedata.category(char) != "Mn")


def squash_text(value):
    return " ".join(value.replace("\r", " ").replace("\n", " ").split())


def display_name(value):
    acronyms = {"api", "erp", "hepa", "llm", "sku"}
    return " ".join(word.upper() if word in acronyms else word.capitalize() for word in value.strip().split())


def decimal_value(value, default=0):
    if value is None:
        return default
    return float(value.replace(",", "."))


def clean_identifier(value):
    return value.strip().strip(".:,;")


def clean_product_name(value):
    return display_name(re.sub(r"^(?:a|al|de|del)\s+", "", value.strip()))


def extract_json_object(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def normalize_llm_result(result):
    intent = result.get("intent", "fallback")
    if intent not in ALLOWED_INTENTS:
        intent = "fallback"

    data = result.get("data") or {}
    if not isinstance(data, dict):
        data = {}

    reply = result.get("reply") or "He interpretado la solicitud."
    return {"intent": intent, "reply": reply, "data": data}


def confirmation_token(intent, reply, data):
    return f"{CONFIRMATION_PREFIX}{json.dumps({'intent': intent, 'reply': reply, 'data': data}, ensure_ascii=True)}"


def confirmation_required_result(intent, reply, data, prompt):
    return {
        "intent": "confirmation_required",
        "reply": prompt,
        "data": {
            "pending_action": intent,
            "confirmation_token": confirmation_token(intent, reply, data),
        },
    }


def parse_confirmation_token(message):
    if not message.startswith(CONFIRMATION_PREFIX):
        return None
    payload = json.loads(message[len(CONFIRMATION_PREFIX) :])
    result = normalize_llm_result(payload)
    result["confirmed"] = True
    return result


def fallback_result(provider_name, user_message, context, reason):
    result = MockLLMProvider().generate_response(user_message, context)
    result["reply"] = f"{result['reply']} (fallback local: {reason})."
    result["provider_status"] = f"Fallback local: {reason}"
    return result


def product_payload(match):
    return {
        "name": display_name(match.group("name")),
        "stock": int(match.group("stock") or 0),
        "unit_price": decimal_value(match.group("price")),
        "description": match.group("description") or "",
        "category": match.group("category") or "",
        "minimum_stock": int(match.group("minimum_stock") or 0),
    }


def integer_from_text(value):
    if value is None:
        return None
    return int(re.search(r"\d+", value).group())


def compact_product_name(value):
    value = re.sub(
        r"\b(y|con|de|del|al|a|el|la|los|las|un|una|unas|unos|producto|productos|llamado|llamada|precio|precios|stock|unidades|unidad|inventario|cuesta|vale)\b",
        " ",
        value,
    )
    value = re.sub(r"(?<![a-z0-9])\d+(?:[.,]\d+)?(?![a-z0-9])", " ", value)
    return " ".join(value.split()).strip()


class MockLLMProvider(BaseLLMProvider):
    name = "mock"

    def generate_response(self, user_message, context):
        self._context = context or {}
        raw_message = squash_text(user_message)
        confirmed_action = parse_confirmation_token(raw_message)
        if confirmed_action:
            return confirmed_action
        lowered = normalize_text(raw_message)
        auto_replenishment_request = self._parse_auto_replenishment_config(lowered)
        if auto_replenishment_request:
            return auto_replenishment_request
        audit_request = self._parse_audit_history_request(lowered)
        if audit_request:
            return audit_request
        operational_query = self._parse_operational_query(lowered)
        if operational_query:
            return operational_query

        if self._is_statistics_request(lowered):
            return {"intent": "show_statistics", "reply": "Consulto las estadísticas del ERP."}

        if self._is_help_request(lowered):
            return {
                "intent": "help",
                "reply": (
                    "Puedo gestionar el ERP por lenguaje natural. Puedes pedirme: "
                    "ver inventario, consultar stock, agregar productos, actualizar precios o unidades, "
                    "registrar proveedores, crear pedidos, registrar desechos y mostrar estadísticas. "
                    "Ejemplos: 'qué productos tengo', 'agrega televisor con precio 300 y 5 unidades', "
                    "'cuántos monitores tengo', 'registra un proveedor llamado TecnoSur con email contacto@tecnosur.com'. "
                    "Para borrar un registro concreto, pídemelo directamente. Si quieres eliminar todo el inventario, te pediré confirmación."
                ),
            }

        dangerous_delete = self._parse_dangerous_inventory_delete(lowered)
        if dangerous_delete:
            return dangerous_delete

        if self._is_confirmed_inventory_delete(lowered):
            return {"intent": "delete_all_products", "reply": "Elimino todo el inventario.", "data": {}}

        if self._is_ambiguous_delete(lowered):
            return {
                "intent": "missing_data",
                "reply": "Indica qué registro quieres eliminar. Por ejemplo: elimina Telefono o elimina el desecho <id>.",
            }

        for parser in [
            self._parse_quick_inventory_add,
            self._parse_create_product,
            self._parse_flexible_create_product,
            self._parse_update_product,
            self._parse_delete_product,
            self._parse_delete_all_suppliers,
            self._parse_create_supplier,
            self._parse_update_supplier,
            self._parse_delete_supplier,
            self._parse_contextual_purchase_order,
            self._parse_create_purchase_order,
            self._parse_update_purchase_order,
            self._parse_delete_purchase_order,
            self._parse_complete_purchase_order,
            self._parse_cancel_latest_purchase_order,
            self._parse_create_waste,
            self._parse_update_waste,
            self._parse_delete_all_waste,
            self._parse_delete_waste,
            self._parse_product_stock_question,
        ]:
            parsed = parser(lowered)
            if parsed:
                return parsed

        list_intent = self._list_intent(lowered)
        if list_intent:
            return {"intent": list_intent, "reply": "Consulto la información solicitada."}

        return {
            "intent": "fallback",
            "reply": (
                "No he identificado una acción exacta. Puedes escribir, por ejemplo: "
                "'crea un producto llamado Filtro HEPA con stock 20 y precio 35', "
                "'lista proveedores', 'crea un pedido al proveedor ClimaSur de 10 unidades de Filtro HEPA' "
                "o 'elimina el desecho <id>'."
            ),
        }

    def _is_statistics_request(self, message):
        return any(term in message for term in ["estadi", "perdida", "perdidas", "resumen"])

    def _is_help_request(self, message):
        return (
            message in ["ayuda", "help", "comandos", "que puedo hacer", "que puedes hacer", "que haces"]
            or "como uso" in message
            or "que cosas puedes" in message
            or "capacidades" in message
        )

    def _last_supplier_name(self):
        return display_name((self._context or {}).get("last_supplier_name", "").strip()) if (self._context or {}).get("last_supplier_name") else None

    def _parse_auto_replenishment_config(self, message):
        if not any(term in message for term in ["reposicion", "reabastecimiento", "pedido automatico", "pedidos automaticos", "genera automaticamente pedidos", "alertas automaticas", "automatizaciones"]):
            return None

        threshold_match = re.search(r"menos de (?P<threshold>\d+) unidades", message)
        threshold = int(threshold_match.group("threshold")) if threshold_match else None
        if any(term in message for term in ["desactiva", "desactivar", "deshabilita", "deshabilitar", "apaga"]):
            return {
                "intent": "configure_auto_replenishment",
                "reply": "Desactivo la reposicion automatica de pedidos.",
                "data": {"enabled": False, "threshold": threshold},
            }

        if any(term in message for term in ["activa", "activar", "habilita", "habilitar", "enciende", "genera automaticamente"]):
            return {
                "intent": "configure_auto_replenishment",
                "reply": "Activo la reposicion automatica de pedidos por stock bajo.",
                "data": {"enabled": True, "threshold": threshold},
            }

        return None

    def _parse_operational_query(self, message):
        if "menos de" in message and "unidades" in message and ("producto" in message or "stock" in message):
            threshold_match = re.search(r"menos de (?P<threshold>\d+) unidades", message)
            return {
                "intent": "query_products",
                "reply": "Consulto productos por debajo del umbral indicado.",
                "data": {"kind": "low_stock", "threshold": int(threshold_match.group("threshold")) if threshold_match else 5},
            }
        if "grafica" in message and "producto" in message and ("menos stock" in message or "menor stock" in message):
            return {"intent": "show_statistics", "reply": "Genero una vista grafica de los productos con menor stock.", "data": {}}
        if "mas stock" in message or "mayor stock" in message:
            return {"intent": "query_products", "reply": "Consulto el producto con mas stock.", "data": {"kind": "most_stock"}}
        if "precio descendente" in message or "por precio descendente" in message:
            return {"intent": "query_products", "reply": "Ordeno los productos por precio descendente.", "data": {"kind": "price_desc"}}
        contains_match = re.search(r"(?:contenga|contengan|contiene|contengan nombre|nombre contenga) [\"“']?(?P<search>.+?)[\"”']?$", message)
        if contains_match and "producto" in message:
            return {
                "intent": "query_products",
                "reply": "Busco productos por nombre.",
                "data": {"kind": "name_contains", "search": contains_match.group("search").strip()},
            }
        if "inventario total" in message or "valor economico total" in message or "vale el inventario" in message or "valor del almacen" in message:
            return {"intent": "query_products", "reply": "Calculo el valor economico del inventario.", "data": {"kind": "inventory_value"}}
        if "agotado" in message or "agotados" in message or "sin stock" in message:
            return {"intent": "query_products", "reply": "Consulto productos agotados.", "data": {"kind": "out_of_stock"}}
        expensive_match = re.search(r"(?P<limit>\d+) productos mas caros", message)
        if expensive_match or "productos mas caros" in message:
            return {
                "intent": "query_products",
                "reply": "Consulto los productos mas caros.",
                "data": {"kind": "top_expensive", "limit": int(expensive_match.group("limit")) if expensive_match else 10},
            }
        if "resumen del inventario" in message or "inventario actual" in message:
            return {"intent": "query_products", "reply": "Preparo un resumen del inventario actual.", "data": {"kind": "summary"}}
        if "pedidos pendientes" in message:
            return {"intent": "query_purchase_orders", "reply": "Consulto los pedidos pendientes.", "data": {"kind": "pending"}}
        if "proveedor" in message and ("mas pedidos" in message or "mas utilizado" in message or "más utilizado" in message):
            return {"intent": "query_purchase_orders", "reply": "Consulto el proveedor con mas pedidos.", "data": {"kind": "top_supplier"}}
        return None

    def _parse_audit_history_request(self, message):
        if not re.search(r"\b(accion|acciones|trazabilidad|auditoria|audit|eliminado|eliminados|borrado|borrados)\b", message):
            return None

        limit_match = re.search(r"(?P<limit>\d+)", message)
        limit = int(limit_match.group("limit")) if limit_match else 10

        if "proveedor" in message:
            if "este proveedor" in message:
                supplier_name = self._last_supplier_name()
                if not supplier_name:
                    return {
                        "intent": "missing_data",
                        "reply": "No tengo un proveedor reciente en memoria. Indica el proveedor sobre el que quieres ver la trazabilidad.",
                    }
            else:
                supplier_match = re.search(r"proveedor (?P<name>.+)$", message)
                supplier_name = display_name(supplier_match.group("name")) if supplier_match else None
                if not supplier_name:
                    return {
                        "intent": "missing_data",
                        "reply": "Indica el proveedor sobre el que quieres consultar la trazabilidad.",
                    }

            return {
                "intent": "show_audit_history",
                "reply": f"Consulto la trazabilidad reciente del proveedor {supplier_name}.",
                "data": {"audit_scope": "supplier", "supplier_name": supplier_name, "limit": limit},
            }

        if "producto" in message and any(term in message for term in ["eliminado", "eliminados", "borrado", "borrados"]):
            return {
                "intent": "show_audit_history",
                "reply": "Consulto la trazabilidad de productos eliminados.",
                "data": {"audit_scope": "deleted_products", "limit": limit},
            }

        return None

    def _parse_dangerous_inventory_delete(self, message):
        if not any(term in message for term in ["elimina", "eliminar", "borra", "borrar", "vacia", "vaciar", "limpia", "limpiar"]):
            return None
        if not any(term in message for term in ["todo", "todos", "toda", "inventario", "almacen", "almacen", "productos"]):
            return None
        if "proveedor" in message or "desecho" in message:
            return None
        if message.startswith("confirma ") or message in ["si", "sí", "s"]:
            return None
        return {
            "intent": "confirmation_required",
            "reply": "Esta acción eliminará todo el inventario de productos. ¿Quieres eliminarlo? Responde sí o no.",
            "data": {"pending_action": "delete_all_products"},
        }

    def _is_confirmed_inventory_delete(self, message):
        return (
            message.startswith("confirma ")
            and any(term in message for term in ["elimina", "eliminar", "borra", "borrar", "vacia", "vaciar", "limpia", "limpiar"])
            and any(term in message for term in ["todo", "todos", "toda", "inventario", "almacen", "productos"])
        )

    def _is_ambiguous_delete(self, message):
        return message in ["elimina", "eliminar", "borra", "borrar", "confirma eliminar", "confirmar eliminar"]

    def _list_intent(self, message):
        if not any(
            term in message
            for term in ["muestrame", "mostrar", "lista", "listar", "ver", "consulta", "que", "cuales", "objetos", "inventario"]
        ):
            return None
        if any(term in message for term in ["producto", "productos", "inventario", "stock", "objetos", "articulos"]):
            return "list_products"
        if "proveedor" in message:
            return "list_suppliers"
        if "pedido" in message or "orden" in message:
            return "list_purchase_orders"
        if "desecho" in message or "merma" in message:
            return "list_waste"
        return None

    def _parse_product_stock_question(self, message):
        match = re.search(
            r"(?:cuantos|cuantas|cuanto|stock de|cantidad de|unidades de) (?P<name>.+?)(?: tengo| hay| quedan| en inventario)?\??$",
            message,
        )
        if not match:
            return None
        name = re.sub(r"\b(tengo|hay|quedan|en inventario|producto|productos|unidades|unidad|de|del|a|al)\b", "", match.group("name")).strip()
        if not name or name in ["producto", "productos", "inventario", "stock"]:
            return None
        return {
            "intent": "get_product_stock",
            "reply": f"Consulto las unidades disponibles de {display_name(name)}.",
            "data": {"name": display_name(name)},
        }

    def _parse_quick_inventory_add(self, message):
        match = re.search(
            r"(?:introduce|introducir|mete|meter|agrega|agregar|anade|anadir|añade|añadir|suma|sumar|registra|registrar) (?P<name>.+?) "
            r"(?:en|al|a el)? ?inventario[, ]+(?P<stock>\d+)(?: unidades)?(?: concretamente)?$",
            message,
        )
        if not match:
            match = re.search(
                r"(?:introduce|introducir|mete|meter|agrega|agregar|anade|anadir|añade|añadir|suma|sumar|registra|registrar) (?P<stock>\d+) "
                r"(?:unidades? )?(?:mas )?(?:de|a|al)? ?(?P<name>.+?)(?: al inventario| en inventario)?$",
                message,
            )
        if not match:
            match = re.search(
                r"(?:mete|pon|carga) (?P<stock>\d+) (?P<name>.+?)(?: al inventario| en inventario)?$",
                message,
            )
        if not match:
            match = re.search(
                r"(?:introduce|introducir|mete|meter|agrega|agregar|anade|anadir|añade|añadir|suma|sumar|registra|registrar) "
                r"(?:al|a el|en el)? ?inventario (?P<name>.+?) (?P<stock>\d+)(?: unidades?)?$",
                message,
            )
        if not match:
            return None
        name = clean_product_name(match.group("name"))
        stock = int(match.group("stock"))
        return {
            "intent": "add_product_stock",
            "reply": f"Registro {stock} unidades de {name} en el inventario.",
            "data": {
                "name": name,
                "quantity": stock,
            },
        }

    def _parse_flexible_create_product(self, message):
        if not any(term in message for term in ["agrega", "agregar", "anade", "añade", "crear", "crea", "registra", "mete", "introduce"]):
            return None
        if not any(term in message for term in ["precio", "cuesta", "vale"]):
            return None
        if not any(term in message for term in ["unidad", "unidades", "stock", "cantidad"]):
            return None

        price_match = re.search(r"(?:precio|precios|cuesta|vale)(?: de)? (?P<price>\d+(?:[.,]\d+)?)", message)
        stock_match = re.search(r"(?P<stock>\d+)\s*(?:unidades|unidad|uds|stock)", message)
        if not stock_match:
            stock_match = re.search(r"(?:stock|cantidad)(?: de)? (?P<stock>\d+)", message)
        if not price_match or not stock_match:
            return None

        name_section = message
        name_section = re.sub(r"^(?:agrega|agregar|anade|añade|crear|crea|registra|mete|introduce)\s+", "", name_section)
        name = compact_product_name(name_section)
        if not name:
            return None

        stock = integer_from_text(stock_match.group("stock"))
        price = decimal_value(price_match.group("price"))
        return {
            "intent": "create_product",
            "reply": f"Registro {display_name(name)} en el inventario.",
            "data": {
                "name": display_name(name),
                "stock": stock,
                "unit_price": price,
                "description": "",
                "category": "Inventario",
                "minimum_stock": 0,
            },
        }

    def _parse_create_product(self, message):
        if any(message.startswith(prefix) for prefix in ["crea producto ", "crear producto ", "registra producto ", "registrar producto "]):
            price_match = re.search(r"precio (?P<price>\d+(?:[.,]\d+)?)", message)
            stock_match = re.search(r"stock (?P<stock>\d+)", message)
            category_match = re.search(r"categoria (?P<category>.+)$", message)
            name = re.sub(r"^(?:crea|crear|registra|registrar) producto\s+", "", message)
            name = re.sub(r"\s+con\s+.*$", "", name).strip()
            missing = []
            if not stock_match:
                missing.append("stock")
            if not price_match:
                missing.append("precio")
            if missing:
                return {
                    "intent": "missing_data",
                    "reply": f"Faltan datos obligatorios para crear el producto: {', '.join(missing)}.",
                }
            data = {
                "name": display_name(name),
                "stock": int(stock_match.group("stock")),
                "unit_price": decimal_value(price_match.group("price")),
                "description": "",
                "category": display_name(category_match.group("category")) if category_match else "",
                "minimum_stock": 0,
            }
            return {"intent": "create_product", "reply": f"Creo el producto {data['name']}.", "data": data}

        match = re.search(
            r"(?:crea|crear|registra|registrar) (?:un )?producto(?: llamado)? (?P<name>.+?)"
            r"(?: con descripcion (?P<description>.+?))?"
            r"(?: en categoria (?P<category>.+?))?"
            r"(?: con stock (?P<stock>\d+))?"
            r"(?: y stock minimo (?P<minimum_stock>\d+))?"
            r"(?: y precio (?P<price>\d+(?:[.,]\d+)?))?$",
            message,
        )
        if not match:
            return None

        data = product_payload(match)
        missing = []
        if match.group("stock") is None:
            missing.append("stock")
        if match.group("price") is None:
            missing.append("precio")
        if missing:
            return {
                "intent": "missing_data",
                "reply": f"Faltan datos obligatorios para crear el producto: {', '.join(missing)}.",
            }
        return {
            "intent": "create_product",
            "reply": f"Creo el producto {data['name']}.",
            "data": data,
        }

    def _parse_update_product(self, message):
        match = re.search(
            r"(?:actualiza|actualizar|modifica|modificar) (?:el )?producto (?P<name>.+?)"
            r"(?: con nombre (?P<new_name>.+?))?"
            r"(?: con stock (?P<stock>\d+))?"
            r"(?: y stock minimo (?P<minimum_stock>\d+))?"
            r"(?: y precio (?P<price>\d+(?:[.,]\d+)?))?"
            r"(?: y categoria (?P<category>.+?))?$",
            message,
        )
        if not match:
            return None
        data = {"name": display_name(match.group("name"))}
        if match.group("new_name"):
            data["new_name"] = display_name(match.group("new_name"))
        if match.group("stock"):
            data["stock"] = int(match.group("stock"))
        if match.group("minimum_stock"):
            data["minimum_stock"] = int(match.group("minimum_stock"))
        if match.group("price"):
            data["unit_price"] = decimal_value(match.group("price"))
        if match.group("category"):
            data["category"] = match.group("category").strip()
        if len(data) == 1:
            return {
                "intent": "missing_data",
                "reply": "Indica al menos un campo para actualizar el producto, por ejemplo stock, precio, nombre o categoría.",
            }
        return {"intent": "update_product", "reply": f"Actualizo el producto {data['name']}.", "data": data}

    def _parse_delete_product(self, message):
        if any(term in message for term in ["proveedor", "pedido", "orden", "desecho", "merma"]):
            return None
        match = re.search(r"(?:confirma )?(?:elimina|eliminar|borra|borrar) (?:el |la )?(?:producto )?(?P<name>.+)$", message)
        if not match:
            return None
        name = display_name(match.group("name"))
        if normalize_text(name) in ["todo", "todos", "toda", "inventario", "almacen", "productos"]:
            return None
        return {"intent": "delete_product", "reply": f"Elimino el producto {name}.", "data": {"name": name}}

    def _parse_create_supplier(self, message):
        match = re.search(
            r"(?:registra|registrar|crea|crear) un proveedor(?: llamado)? (?P<name>.+?)"
            r"(?:\s+(?:con\s+)?(?:email|correo|cif|nif|tax id|telefono|teléfono|direccion|dirección)\b|$)",
            message,
        )
        if not match:
            return None
        email_match = re.search(r"(?:email|correo)\s+(?P<email>[^\s,;]+@[^\s,;]+)", message)
        tax_match = re.search(r"(?:cif|nif|tax id)\s+(?P<tax>[a-z0-9-]+)", message)
        phone_match = re.search(r"(?:telefono|teléfono|tlf)\s+(?P<phone>[\d+ ]+)", message)
        address_match = re.search(r"(?:direccion|dirección)\s+(?P<address>.+?)(?:\s+y?\s*(?:email|correo|cif|nif|tax id|telefono|teléfono)\b|$)", message)
        if not email_match:
            return {
                "intent": "missing_data",
                "reply": "Falta el email del proveedor. Ejemplo: registra un proveedor llamado ClimaSur con email contacto@climasur.com.",
            }
        name = display_name(match.group("name"))
        return {
            "intent": "create_supplier",
            "reply": f"Registro el proveedor {name}.",
            "data": {
                "name": name,
                "contact_email": email_match.group("email").strip(),
                "tax_id": (tax_match.group("tax") if tax_match else "").upper(),
                "phone": (phone_match.group("phone") if phone_match else "").strip(),
                "address": (address_match.group("address") if address_match else "").strip(),
                "products_supplied": [],
            },
        }

    def _parse_update_supplier(self, message):
        phone_only = re.search(r"(?:actualiza|actualizar|modifica|modificar) (?:el )?telefono de (?P<name>.+?) a (?P<phone>[\d+ ]+)$", message)
        if phone_only:
            return {
                "intent": "update_supplier",
                "reply": f"Actualizo el proveedor {display_name(phone_only.group('name'))}.",
                "data": {"name": display_name(phone_only.group("name")), "phone": phone_only.group("phone").strip()},
            }
        match = re.search(
            r"(?:actualiza|actualizar|modifica|modificar) (?:el )?proveedor (?P<name>.+?)"
            r"(?:\s+(?:con\s+)?(?:nombre|email|correo|cif|nif|tax id|telefono|teléfono|direccion|dirección)\b|$)",
            message,
        )
        if not match:
            return None
        data = {"name": display_name(match.group("name"))}
        new_name_match = re.search(r"(?:nombre)\s+(?P<new_name>.+?)(?:\s+(?:con\s+)?(?:email|correo|cif|nif|tax id|telefono|teléfono|direccion|dirección)\b|$)", message)
        email_match = re.search(r"(?:email|correo)\s+(?P<email>[^\s,;]+@[^\s,;]+)", message)
        tax_match = re.search(r"(?:cif|nif|tax id)\s+(?P<tax>[a-z0-9-]+)", message)
        phone_match = re.search(r"(?:telefono|teléfono|tlf)\s+(?P<phone>[\d+ ]+)", message)
        address_match = re.search(r"(?:direccion|dirección)\s+(?P<address>.+?)(?:\s+y?\s*(?:email|correo|cif|nif|tax id|telefono|teléfono)\b|$)", message)
        if new_name_match:
            data["new_name"] = display_name(new_name_match.group("new_name"))
        if email_match:
            data["contact_email"] = email_match.group("email")
        if tax_match:
            data["tax_id"] = tax_match.group("tax").upper()
        if phone_match:
            data["phone"] = phone_match.group("phone").strip()
        if address_match:
            data["address"] = address_match.group("address").strip()
        if len(data) == 1:
            return {
                "intent": "missing_data",
                "reply": "Indica al menos un campo para actualizar el proveedor, por ejemplo email, teléfono, dirección o nombre.",
            }
        return {"intent": "update_supplier", "reply": f"Actualizo el proveedor {data['name']}.", "data": data}

    def _parse_delete_supplier(self, message):
        match = re.search(r"(?:confirma )?(?:elimina|eliminar|borra|borrar) (?:el )?proveedor (?P<name>.+)$", message)
        if not match:
            return None
        name = display_name(match.group("name"))
        return {"intent": "delete_supplier", "reply": f"Elimino el proveedor {name}.", "data": {"name": name}}

    def _parse_delete_all_suppliers(self, message):
        if not any(term in message for term in ["elimina", "eliminar", "borra", "borrar"]):
            return None
        if not ("proveedor" in message and any(term in message for term in ["todo", "todos"])):
            return None
        return {
            "intent": "confirmation_required",
            "reply": "Esta accion eliminara todos los proveedores sin pedidos asociados. Quieres continuar? Responde si o no.",
            "data": {"pending_action": "delete_all_suppliers", "confirmation_token": confirmation_token("delete_all_suppliers", "Elimino todos los proveedores.", {})},
        }

    def _parse_create_purchase_order(self, message):
        match = re.search(
            r"(?:crea|crear|registra|registrar) un pedido al proveedor (?P<supplier>.+?) "
            r"de (?P<quantity>\d+) unidades de (?P<product>.+?)(?: a precio (?P<price>\d+(?:[.,]\d+)?))?$",
            message,
        )
        if not match:
            return None
        supplier = display_name(match.group("supplier"))
        product = display_name(match.group("product"))
        item = {"product_name": product, "quantity": int(match.group("quantity"))}
        if match.group("price"):
            item["unit_price"] = decimal_value(match.group("price"))
        return {
            "intent": "create_purchase_order",
            "reply": f"Registro un pedido a {supplier}.",
            "data": {"supplier_name": supplier, "items": [item]},
        }

        
    def _parse_contextual_purchase_order(self, message):
        match = re.search(
            r"(?:haz|hacer|crea|crear|creale|registra|registrar)(?:le)? un pedido "
            r"de (?P<quantity>\d+)(?: unidades(?: de)? )?(?P<product>.+?)(?: a precio (?P<price>\d+(?:[.,]\d+)?))?$",
            message,
        )
        if not match:
            return None

        supplier = self._last_supplier_name()
        if not supplier:
            return {
                "intent": "missing_data",
                "reply": "No tengo un proveedor reciente en memoria. Indica el nombre del proveedor para crear el pedido.",
            }

        product = display_name(match.group("product"))
        item = {"product_name": product, "quantity": int(match.group("quantity"))}
        if match.group("price"):
            item["unit_price"] = decimal_value(match.group("price"))

        return {
            "intent": "create_purchase_order",
            "reply": f"Registro un pedido a {supplier}.",
            "data": {"supplier_name": supplier, "items": [item]},
        }

    def _parse_update_purchase_order(self, message):
        match = re.search(
            r"(?:actualiza|actualizar|modifica|modificar) (?:el )?pedido (?P<id>[a-f0-9]{6,24}) "
            r"al proveedor (?P<supplier>.+?) de (?P<quantity>\d+) unidades de (?P<product>.+?)"
            r"(?: con estado (?P<status>[\w -]+))?$",
            message,
        )
        if not match:
            return None
        return {
            "intent": "update_purchase_order",
            "reply": "Actualizo el pedido indicado.",
            "data": {
                "id": clean_identifier(match.group("id")),
                "supplier_name": display_name(match.group("supplier")),
                "items": [
                    {
                        "product_name": display_name(match.group("product")),
                        "quantity": int(match.group("quantity")),
                    }
                ],
                "status": (match.group("status") or "received").strip(),
            },
        }

    def _parse_complete_purchase_order(self, message):
        match = re.search(r"(?:marca|marcar) (?:el )?pedido (?P<id>[a-f0-9]{1,24}) como completado", message)
        if not match:
            return None
        return {"intent": "complete_purchase_order", "reply": "Marco el pedido como completado.", "data": {"id": clean_identifier(match.group("id"))}}

    def _parse_cancel_latest_purchase_order(self, message):
        if "ultimo pedido" in message and any(term in message for term in ["cancela", "cancelar", "anula", "anular"]):
            return {"intent": "cancel_latest_purchase_order", "reply": "Cancelo el ultimo pedido creado.", "data": {}}
        return None

    def _parse_delete_purchase_order(self, message):
        match = re.search(r"(?:confirma )?(?:elimina|eliminar|borra|borrar) (?:el )?pedido (?P<id>[a-f0-9]{6,24})", message)
        if not match:
            return None
        return {"intent": "delete_purchase_order", "reply": "Elimino el pedido indicado.", "data": {"id": clean_identifier(match.group("id"))}}

    def _parse_create_waste(self, message):
        match = re.search(
            r"(?:registra|registrar|crea|crear) un desecho de (?P<quantity>\d+) unidades de (?P<product>.+?)"
            r"(?: por (?P<reason>caducidad|producto danado|ajuste manual))?$",
            message,
        )
        if not match:
            return None
        reason = (match.group("reason") or "ajuste manual").replace("danado", "dañado")
        return {
            "intent": "create_waste",
            "reply": f"Registro el desecho de {display_name(match.group('product'))}.",
            "data": {
                "product_name": display_name(match.group("product")),
                "quantity": int(match.group("quantity")),
                "reason": reason,
            },
        }

    def _parse_update_waste(self, message):
        match = re.search(
            r"(?:actualiza|actualizar|modifica|modificar) (?:el )?desecho (?P<id>[a-f0-9]{6,24}) "
            r"a (?P<quantity>\d+) unidades de (?P<product>.+?) por (?P<reason>caducidad|producto danado|ajuste manual)$",
            message,
        )
        if not match:
            return None
        reason = match.group("reason").replace("danado", "dañado")
        return {
            "intent": "update_waste",
            "reply": "Actualizo el desecho indicado.",
            "data": {
                "id": clean_identifier(match.group("id")),
                "product_name": display_name(match.group("product")),
                "quantity": int(match.group("quantity")),
                "reason": reason,
            },
        }

    def _parse_delete_waste(self, message):
        match = re.search(r"(?:confirma )?(?:elimina|eliminar|borra|borrar) (?:el )?desecho (?P<id>[a-f0-9]{6,24})", message)
        if not match:
            return None
        return {"intent": "delete_waste", "reply": "Elimino el desecho indicado.", "data": {"id": clean_identifier(match.group("id"))}}

    def _parse_delete_all_waste(self, message):
        if not any(term in message for term in ["elimina", "eliminar", "borra", "borrar"]):
            return None
        if not ("desecho" in message and any(term in message for term in ["todo", "todos", "registrados"])):
            return None
        return {
            "intent": "confirmation_required",
            "reply": "Esta accion eliminara todos los desechos registrados. Quieres continuar? Responde si o no.",
            "data": {"pending_action": "delete_all_waste", "confirmation_token": confirmation_token("delete_all_waste", "Elimino todos los desechos registrados.", {})},
        }


class OpenAIProvider(BaseLLMProvider):
    name = "openai"

    def generate_response(self, user_message, context):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return fallback_result("OpenAI", user_message, context, "sin clave OpenAI")

        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        payload = {
            "model": model,
            "instructions": SYSTEM_PROMPT,
            "input": user_message,
            "max_output_tokens": 450,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "erp_intent",
                    "schema": RESPONSE_SCHEMA,
                    "strict": False,
                }
            },
        }
        try:
            response = requests.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=25,
            )
            response.raise_for_status()
            body = response.json()
            text = body.get("output_text") or _openai_output_text(body)
            result = normalize_llm_result(extract_json_object(text))
            result["provider_status"] = f"API real: {model}"
            return result
        except Exception as exc:
            return fallback_result("OpenAI", user_message, context, f"error OpenAI: {exc}")


class GeminiProvider(BaseLLMProvider):
    name = "gemini"

    def __init__(self, model=None):
        self.model = model

    def generate_response(self, user_message, context):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return fallback_result("Gemini", user_message, context, "sin clave Gemini")

        model = self.model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": user_message}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": RESPONSE_SCHEMA,
                "temperature": 0.1,
                "maxOutputTokens": 450,
            },
        }
        try:
            response = requests.post(
                url,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=25,
            )
            response.raise_for_status()
            body = response.json()
            text = body["candidates"][0]["content"]["parts"][0]["text"]
            result = normalize_llm_result(extract_json_object(text))
            result["provider_status"] = f"API real: {model}"
            return result
        except Exception as exc:
            return fallback_result("Gemini", user_message, context, f"error Gemini: {exc}")


class ClaudeProvider(BaseLLMProvider):
    name = "claude"

    def generate_response(self, user_message, context):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return fallback_result("Claude", user_message, context, "sin clave Claude")

        model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
        payload = {
            "model": model,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_message}],
            "max_tokens": 450,
            "temperature": 0.1,
        }
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
                timeout=25,
            )
            response.raise_for_status()
            body = response.json()
            text = "".join(part.get("text", "") for part in body.get("content", []) if part.get("type") == "text")
            result = normalize_llm_result(extract_json_object(text))
            result["provider_status"] = f"API real: {model}"
            return result
        except Exception as exc:
            return fallback_result("Claude", user_message, context, f"error Claude: {exc}")


class LocalLLMProvider(BaseLLMProvider):
    name = "local"

    def generate_response(self, user_message, context):
        if not os.getenv("LOCAL_LLM_URL"):
            result = MockLLMProvider().generate_response(user_message, context)
            result["reply"] = f"{result['reply']} (simulado sin modelo local)."
            return result
        return MockLLMProvider().generate_response(user_message, context)


def get_provider(provider_name=None):
    selected = (provider_name or os.getenv("DEFAULT_LLM_PROVIDER", "mock")).lower()
    gemini_models = {
        "gemini": "gemini-2.5-flash",
        "gemini-2.5-flash": "gemini-2.5-flash",
        "gemini-2.5-flash-lite": "gemini-2.5-flash-lite",
        "gemini-2.0-flash": "gemini-2.0-flash",
    }
    if selected in gemini_models:
        return GeminiProvider(model=gemini_models[selected])

    providers = {
        "mock": MockLLMProvider(),
        "openai": OpenAIProvider(),
        "claude": ClaudeProvider(),
        "local": LocalLLMProvider(),
    }
    return providers.get(selected, providers["mock"])


def _openai_output_text(body):
    chunks = []
    for output in body.get("output", []):
        for content in output.get("content", []):
            if content.get("type") in ["output_text", "text"]:
                chunks.append(content.get("text", ""))
    return "".join(chunks)
