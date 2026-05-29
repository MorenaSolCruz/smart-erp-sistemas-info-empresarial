import os
import json
import re
import unicodedata
from difflib import get_close_matches
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
    "receive_purchase_order",
    "cancel_purchase_order",
    "update_purchase_order",
    "delete_purchase_order",
    "delete_all_purchase_orders",
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
            "description": "Acción ERP que debe ejecutar el backend.",
        },
        "reply": {
            "type": "string",
            "description": "Respuesta breve en español para el usuario.",
        },
        "data": {
            "type": "object",
            "description": "Datos necesarios para ejecutar la acción. Usar objeto vacío si no aplica.",
            "additionalProperties": True,
        },
    },
    "required": ["intent", "reply", "data"],
    "additionalProperties": False,
}

CONFIRMATION_PREFIX = "confirm_action::"
LLM_ERROR_MESSAGE = "El LLM no pudo procesar la solicitud, contacte con el administrador."


SYSTEM_PROMPT = """
Eres Maja, el clasificador de intenciones de un prototipo ERP conversacional.
Tu única salida debe ser JSON válido con esta forma:
{"intent": "...", "reply": "...", "data": {...}}

No ejecutes operaciones por tu cuenta. Solo interpreta el mensaje del usuario.
El backend ejecutará la operación indicada.
Tu trabajo es entender lenguaje natural aunque el usuario escriba con faltas,
sin tildes, con palabras incompletas o en orden distinto.

Intenciones permitidas:
- help
- confirmation_required
- missing_data
- fallback
- list_products, create_product, add_product_stock, update_product, delete_product, delete_all_products
- get_product_stock para preguntas como "cuántos monitores tengo" o "stock de Filtro HEPA"
- list_suppliers, create_supplier, update_supplier, delete_supplier
- list_purchase_orders, create_purchase_order, receive_purchase_order, cancel_purchase_order, update_purchase_order, delete_purchase_order
- list_waste, create_waste, update_waste, delete_waste
- show_statistics
- show_audit_history para trazabilidad y auditoría
- configure_auto_replenishment para activar o desactivar la reposición automática

Reglas de seguridad:
- Para eliminar un producto, proveedor, pedido o desecho concreto, usa delete_* directamente.
- Solo pide confirmation_required si el usuario quiere eliminar todo el inventario, todo el almacén,
  todos los productos o todos los registros de productos.
- Si el usuario mezcla varias acciones o condiciones en la misma frase, no adivines. Usa missing_data y pide que lo separe en pasos.
- Si faltan campos obligatorios, usa missing_data.
- Si la intención no es clara, usa fallback.
- Si el usuario pregunta que puedes hacer, ejemplos, ayuda, comandos o capacidades, usa help.
- Si pregunta "qué productos tengo", "que hay en inventario", "objetos en stock", usa list_products.
- Si pregunta "cuantos monitores tengo", "stock de tablets", "cantidad de teléfono", usa get_product_stock.
- Si dice "agrega", "añade", "mete", "introduce", "registra" un producto con unidades/precio,
  interpreta create_product o add_product_stock según corresponda.
- Si da precio y unidades para un producto nuevo, usa create_product.
- Si solo da unidades para un producto, usa add_product_stock.

Campos esperados por intención:
- create_product: data.name, data.stock, data.unit_price. Opcionales: description, category, minimum_stock.
- add_product_stock: data.name, data.quantity. Si el producto no existe, el backend puede crearlo con precio 0.
- update_product: data.name y al menos uno de new_name, stock, unit_price, category, minimum_stock.
- delete_product: data.name. Opcional: data.quantity si solo quiere borrar una cantidad del stock.
- delete_all_products: data debe ser {}.
- get_product_stock: data.name.
- create_supplier: data.name, data.contact_email. Opcionales: phone, address, products_supplied, cif.
- update_supplier: data.name y al menos uno de new_name, contact_email, phone, address.
- delete_supplier: data.name.
- create_purchase_order: data.supplier_name, data.items. Cada item necesita product_name y quantity. unit_price opcional.
- receive_purchase_order: data.supplier_name o data.id. Opcional: data.items si la recepción es parcial.
- cancel_purchase_order: data.supplier_name o data.id. Opcional: data.reason.
- update_purchase_order: data.id, data.supplier_name, data.items. status opcional.
- delete_purchase_order: data.id.
- create_waste: data.product_name, data.quantity, data.reason. reason debe ser caducidad, producto dañado o ajuste manual.
- update_waste: data.id, data.product_name, data.quantity, data.reason.
- delete_waste: data.id.
- show_audit_history: data.audit_scope, data.limit y según el caso data.supplier_name.
- configure_auto_replenishment: data.enabled con valor true o false.
- list_* y show_statistics: data debe ser {}.

Normaliza nombres propios de productos y proveedores con mayúsculas profesionales.
Responde siempre en español profesional y breve.

Ejemplos de interpretación:
- "agrega televisor con precio 300 y 5 unidades" -> create_product con name Televisor, stock 5, unit_price 300.
- "mete 10 ratones al inventario" -> add_product_stock con name Ratones, quantity 10.
- "cuántos monitores tengo?" -> get_product_stock con name Monitores.
- "qué hay en el inventario?" -> list_products.
- "quiero ver proveedores" -> list_suppliers.
- "haz un pedido a ClimaSur de 8 filtros HEPA" -> create_purchase_order.
- "recibimos el pedido del proveedor ClimaSur" -> receive_purchase_order.
- "cancela el pedido del proveedor ClimaSur" -> cancel_purchase_order.
- "borra el producto Tablet" -> delete_product.
- "elimina teléfono" -> delete_product con name Teléfono.
- "borra 3 filtros hepa" -> delete_product con name Filtro Hepa, quantity 3.
- "elimina todo el inventario" -> confirmation_required con data.pending_action delete_all_products.
- "confirma eliminar todo el inventario" -> delete_all_products.
- "muéstrame las últimas 10 acciones sobre este proveedor" -> show_audit_history.
- "dime los últimos 35 productos eliminados" -> show_audit_history.
""".strip()


class BaseLLMProvider:
    name = "base"

    def generate_response(self, user_message, context):
        raise NotImplementedError


def build_contextual_user_message(user_message, context):
    context = context or {}
    context_lines = []

    if context.get("last_supplier_name"):
        context_lines.append(f"- ultimo_proveedor: {context['last_supplier_name']}")
    if context.get("last_product_name"):
        context_lines.append(f"- ultimo_producto: {context['last_product_name']}")

    pending_action = context.get("pending_action")
    if isinstance(pending_action, dict) and pending_action.get("intent"):
        context_lines.append(f"- accion_pendiente: {pending_action['intent']}")

    if not context_lines:
        return user_message

    return (
        "Contexto conversacional actual:\n"
        + "\n".join(context_lines)
        + "\n\nUsa este contexto solo cuando el usuario haga referencias como "
        "'creale', 'hazle', 'este proveedor' o equivalentes.\n\n"
        + f"Mensaje del usuario:\n{user_message}"
    )


def normalize_text(value):
    value = unicodedata.normalize("NFD", value.strip().lower())
    return "".join(char for char in value if unicodedata.category(char) != "Mn")

def normalize_key(value):
    value = unicodedata.normalize("NFD", value.strip().lower())
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def singularize_basic(value):
    words = value.split()
    result = []

    for word in words:
        if word.endswith("es") and len(word) > 4:
            result.append(word[:-2])
        elif word.endswith("s") and len(word) > 3:
            result.append(word[:-1])
        else:
            result.append(word)

    return " ".join(result)


def product_search_keys(value):
    normalized = normalize_key(value)
    singular = normalize_key(singularize_basic(normalized))

    return list(dict.fromkeys([
        normalized,
        singular,
    ]))

def display_name(value):
    value = re.sub(r"^(?:llamado|llamada)\s+", "", value.strip(), flags=re.IGNORECASE)
    acronyms = {"api", "erp", "hepa", "llm", "sku"}
    return " ".join(word.upper() if word in acronyms else word.capitalize() for word in value.split())


def decimal_value(value, default=0):
    if value is None:
        return default
    return float(value.replace(",", "."))


def clean_identifier(value):
    return value.strip().strip(".:,;")

def clean_text_field(value):
    if not value:
        return ""
    return value.strip().strip(".,;")


def extract_email(message):
    match = re.search(r"\bemail\s+(?P<email>\S+)", message)
    return clean_text_field(match.group("email")) if match else None


def extract_phone(message):
    match = re.search(r"\b(?:telefono|tlf|tel)\s+(?P<phone>[\d+ ]+)", message)
    if not match:
        match = re.search(r"\bcon el telefono\s+(?P<phone>[\d+ ]+)", message)
    return clean_text_field(match.group("phone")) if match else ""

def extract_cif(message):
    match = re.search(r"\bcif\s+(?P<cif>[a-z0-9]+)", message, flags=re.IGNORECASE)
    return match.group("cif").upper() if match else ""


def extract_number_after_keywords(message, keywords):
    pattern = rf"\b(?:{'|'.join(keywords)})\s+(?P<number>\d+(?:[.,]\d+)?)"
    match = re.search(pattern, message)
    return decimal_value(match.group("number")) if match else None


def extract_int_after_keywords(message, keywords):
    value = extract_number_after_keywords(message, keywords)
    return int(value) if value is not None else None

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
    return {
        "intent": "fallback",
        "reply": LLM_ERROR_MESSAGE,
        "data": {},
        "provider_status": f"LLM unavailable: {provider_name} ({reason})",
        "llm_error": True,
    }


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
        r"\b(y|con|de|del|al|a|el|la|los|las|un|una|unas|unos|producto|productos|precio|precios|stock|unidades|unidad|inventario|cuesta|vale|llamado|llamada)\b",
        " ",
        value,
    )
    value = re.sub(r"\d+(?:[.,]\d+)?", " ", value)
    return " ".join(value.split()).strip()


def looks_like_new_command(message):
    return bool(
        re.search(
            r"^(?:introduce|introducir|meter|mete|agrega|agregar|anade|anadir|añade|sumar|registra|registrar|"
            r"crea|crear|actualiza|actualizar|modifica|modificar|borra|borrar|elimina|eliminar|muestra|"
            r"mostrar|lista|listar|consulta|cuantos|cuantas|cuanto|haz|hacer|pide|pedir|recibimos|recibido|"
            r"cancela|cancelar|anula|anular|marca|marcar)\b",
            message,
        )
    )


def is_full_inventory_delete_request(message):
    explicit_full_scope_patterns = [
        r"\b(?:elimina|eliminar|borra|borrar)\b.*\b(?:todo|todos|toda)\b.*\b(?:inventario|almacen|productos)\b",
        r"\b(?:vaciar|limpiar)\b.*\b(?:inventario|almacen|productos)\b",
    ]
    return any(re.search(pattern, message) for pattern in explicit_full_scope_patterns)


def detect_compound_request(message):
    normalized = f" {message.strip()} "
    action_patterns = {
        "inventory_read": r"\b(?:muestrame|muestra|mostrar|lista|listar|ver|consulta|stock de|cantidad de|cuantos|cuantas|cuanto)\b",
        "inventory_write": r"\b(?:agrega|anade|mete|introduce|crea|crear|actualiza|modifica|borra|elimina|vaciar|limpiar)\b",
        "supplier": r"\b(?:proveedor|proveedores)\b",
        "purchase_order": r"\b(?:pedido|pedidos|pedir|pide|recibimos|recibido|cancela|anula)\b",
        "waste": r"\b(?:desecho|merma)\b",
    }
    matched_categories = [name for name, pattern in action_patterns.items() if re.search(pattern, normalized)]

    multi_connector_patterns = [
        r"\b(?:y luego|luego|despues|despues de eso|ademas)\b",
        r"\bsi\b.+\b(?:entonces|borra|elimina|crea|pide|muestra|lista|actualiza)\b",
    ]
    has_compound_connector = any(re.search(pattern, normalized) for pattern in multi_connector_patterns)

    multiple_action_verbs = len(
        re.findall(
            r"\b(?:agrega|anade|mete|introduce|crea|crear|actualiza|modifica|borra|elimina|pide|pedir|recibimos|recibido|cancela|anula|muestra|lista|ver|consulta)\b",
            normalized,
        )
    ) >= 2

    if has_compound_connector and multiple_action_verbs:
        return {
            "intent": "missing_data",
            "reply": (
                "He detectado varias acciones en la misma solicitud. Para evitar errores, pásamelas por separado, "
                "por ejemplo primero el pedido y luego el borrado."
            ),
            "data": {"reason": "compound_request"},
        }

    conditional_follow_up = re.search(
        r"\b(?:si|cuando)\b.+\b(?:borra|elimina|crea|pide|muestra|lista|actualiza|cancela|recibe|recibimos)\b",
        normalized,
    )
    if conditional_follow_up and multiple_action_verbs:
        return {
            "intent": "missing_data",
            "reply": (
                "He detectado una solicitud condicional con varias acciones. Para evitar resultados no deseados, "
                "indícame primero una sola operación."
            ),
            "data": {"reason": "conditional_request"},
        }

    multiple_list_targets = re.search(
        r"\b(?:producto|productos|proveedor|proveedores|pedido|pedidos|desecho|desechos|merma|mermas)\b.+\by\b.+"
        r"\b(?:producto|productos|proveedor|proveedores|pedido|pedidos|desecho|desechos|merma|mermas)\b",
        normalized,
    )
    if multiple_list_targets and re.search(r"\b(?:muestrame|muestra|mostrar|lista|listar|ver|consulta)\b", normalized):
        return {
            "intent": "missing_data",
            "reply": (
                "He detectado varias consultas en la misma frase. Para evitar ambigüedades, pídeme primero una sola lista, "
                "por ejemplo productos o proveedores."
            ),
            "data": {"reason": "multi_target_query"},
        }

    return None


class MockLLMProvider(BaseLLMProvider):
    name = "mock"

    def generate_response(self, user_message, context):
        self._context = context or {}
        raw_message = user_message.strip()
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

        compound_request = detect_compound_request(lowered)
        if compound_request:
            return compound_request

        dangerous_delete = self._parse_dangerous_inventory_delete(lowered)
        if dangerous_delete:
            return dangerous_delete

        if self._is_confirmed_inventory_delete(lowered):
            return {"intent": "delete_all_products", "reply": "Elimino todo el inventario.", "data": {}}

        if self._is_ambiguous_delete(lowered):
            return {
                "intent": "missing_data",
                "reply": "Indica qué registro quieres eliminar. Por ejemplo: elimina Teléfono o elimina el desecho <id>.",
            }

        for parser in [
            self._parse_pending_duplicate_update,
            self._parse_pending_product_selection,
            self._parse_product_supplier_question,
            self._parse_pending_purchase_orders,
            self._parse_quick_inventory_add_v2,
            self._parse_quick_inventory_add,
            self._parse_flexible_create_product,
            self._parse_contextual_purchase_order_v2,
            self._parse_contextual_purchase_order_v3,
            self._parse_contextual_purchase_order,
            self._parse_create_purchase_order,
            self._parse_receive_purchase_order,
            self._parse_cancel_purchase_order,
            self._parse_product_stock_question,
            self._parse_create_product,
            self._parse_update_product,
            self._parse_delete_product,
            self._parse_supplier_details,
            self._parse_create_supplier,
            self._parse_update_supplier_phone_direct,
            self._parse_update_supplier,
            self._parse_delete_supplier,
            self._parse_delete_all_suppliers,
            self._parse_update_purchase_order,
            self._parse_delete_purchase_order,
            self._parse_delete_all_purchase_orders,
            self._parse_complete_purchase_order,
            self._parse_cancel_latest_purchase_order,
            self._parse_create_waste,
            self._parse_update_waste,
            self._parse_delete_waste,
            self._parse_delete_all_waste,
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
        if not any(term in message for term in ["reposicion", "reabastecimiento", "pedido automatico", "pedidos automaticos"]):
            return None

        if any(term in message for term in ["activa", "activar", "habilita", "habilitar", "enciende"]):
            return {
                "intent": "configure_auto_replenishment",
                "reply": "Activo la reposición automática de pedidos por stock bajo.",
                "data": {"enabled": True},
            }

        if any(term in message for term in ["desactiva", "desactivar", "deshabilita", "deshabilitar", "apaga"]):
            return {
                "intent": "configure_auto_replenishment",
                "reply": "Desactivo la reposición automática de pedidos.",
                "data": {"enabled": False},
            }

        return None

    def _parse_audit_history_request(self, message):
        if not any(term in message for term in ["accion", "acciones", "trazabilidad", "auditoria", "audit", "eliminad"]):
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
        if not any(term in message for term in ["elimina", "eliminar", "borra", "borrar", "vaciar", "limpiar"]):
            return None
        if not is_full_inventory_delete_request(message):
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
            and any(term in message for term in ["elimina", "eliminar", "borra", "borrar", "vaciar", "limpiar"])
            and is_full_inventory_delete_request(message)
        )

    def _is_ambiguous_delete(self, message):
        return message in ["elimina", "eliminar", "borra", "borrar", "confirma eliminar", "confirmar eliminar"]

    def _parse_product_supplier_question(self, message):
        match = re.search(
            r"(?:a que proveedor|con que proveedor|proveedor).*?(?:se asocia|esta asociado|tiene).*?(?P<product>.+)$",
            message,
        )
        if not match:
            return None

        return {
            "intent": "missing_data",
            "reply": "Los productos no se asocian automáticamente a un proveedor al crearlos. Crea un pedido a un proveedor para vincularlo operativamente.",
            "data": {"product_name": display_name(match.group("product"))},
        }

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

    def _parse_operational_query(self, message):
        if any(term in message for term in ["stock bajo", "poco stock", "bajo stock"]):
            threshold = extract_int_after_keywords(message, ["de", "a", "menor que"])
            return {
                "intent": "query_products",
                "reply": "Consulto los productos con stock bajo.",
                "data": {"kind": "low_stock", "threshold": threshold},
            }
        if "mas stock" in message or "mayor stock" in message:
            return {"intent": "query_products", "reply": "Consulto el producto con mas stock.", "data": {"kind": "most_stock"}}
        if "precio" in message and any(term in message for term in ["desc", "caro", "caros", "mayor"]):
            return {"intent": "query_products", "reply": "Ordeno los productos por precio descendente.", "data": {"kind": "price_desc"}}
        if any(
            term in message
            for term in [
                "valor del inventario",
                "valor inventario",
                "cuanto vale el inventario total",
                "cuanto vale inventario total",
                "vale el inventario total",
            ]
        ):
            return {"intent": "query_products", "reply": "Calculo el valor total del inventario.", "data": {"kind": "inventory_value"}}
        if "agotad" in message:
            return {"intent": "query_products", "reply": "Consulto productos agotados.", "data": {"kind": "out_of_stock"}}
        if any(term in message for term in ["resumen inventario", "resumen del inventario"]):
            return {"intent": "query_products", "reply": "Preparo un resumen del inventario actual.", "data": {"kind": "summary"}}
        if "pedidos pendientes" in message:
            return {"intent": "query_purchase_orders", "reply": "Consulto los pedidos pendientes.", "data": {"kind": "pending"}}
        if any(term in message for term in ["proveedor con mas pedidos", "proveedor con más pedidos"]):
            return {"intent": "query_purchase_orders", "reply": "Consulto el proveedor con mas pedidos.", "data": {"kind": "top_supplier"}}
        return None

    def _parse_pending_purchase_orders(self, message):
        if not any(term in message for term in ["pedido", "pedidos"]):
            return None
        if not any(term in message for term in ["pendiente", "pendientes", "falta", "faltan", "recibir", "recepcion"]):
            return None
        if not any(term in message for term in ["muestrame", "muestra", "mostrar", "lista", "listar", "ver", "consulta", "que", "cuales"]):
            return None
        return {
            "intent": "list_purchase_orders",
            "reply": "Consulto los pedidos pendientes de recibir.",
            "data": {"status": "pending"},
        }

    def _parse_product_stock_question(self, message):
        if any(term in message for term in ["elimina", "eliminar", "borra", "borrar", "pedido", "pedir"]):
            return None
        match = re.search(
            r"(?:cuantos|cuantas|cuanto|stock de|cantidad de|unidades de) (?P<name>.+?)(?: tengo| hay| quedan| en inventario)?\??$",
            message,
        )
        if not match:
            return None
        name = re.sub(r"\b(tengo|hay|quedan|en inventario|producto|productos|unidades)\b", "", match.group("name")).strip()
        if not name or name in ["producto", "productos", "inventario", "stock"]:
            return None
        return {
            "intent": "get_product_stock",
            "reply": f"Consulto las unidades disponibles de {display_name(name)}.",
            "data": {"name": display_name(name)},
        }

    def _parse_quick_inventory_add_v2(self, message):
        patterns = [
            r"(?:introduce|introducir|meter|mete|agrega|agregar|anade|anadir|sumar|registra|registrar) (?P<name>.+?) "
            r"(?:en|al|a el)? ?inventario[, ]+(?P<stock>\d+)(?: unidades)?(?: concretamente)?$",
            r"(?:introduce|introducir|meter|mete|agrega|agregar|anade|anadir|sumar|registra|registrar) (?P<stock>\d+) "
            r"(?:unidades?(?: de)? )?(?P<name>.+?)(?: al inventario| en inventario)?$",
            r"(?:mete|pon|carga) (?P<stock>\d+) (?P<name>.+?)(?: al inventario| en inventario)?$",
        ]
        for pattern in patterns:
            match = re.search(pattern, message)
            if not match:
                continue
            raw_name = re.sub(r"^(?:de\s+)?", "", match.group("name")).strip()
            name = display_name(raw_name)
            stock = int(match.group("stock"))
            return {
                "intent": "add_product_stock",
                "reply": f"Registro {stock} unidades de {name} en el inventario.",
                "data": {
                    "name": name,
                    "quantity": stock,
                },
            }
        return None

    def _parse_contextual_purchase_order_v2(self, message):
        patterns = [
            r"(?:haz|hacer|crea|crear|genera|generar|registra|registrar|pide|pedir)(?:me|le)? un pedido "
            r"de (?P<quantity>\d+) unidades de (?P<product>.+?)(?: a precio (?P<price>\d+(?:[.,]\d+)?))?$",
            r"(?:haz|hacer|crea|crear|genera|generar|registra|registrar|pide|pedir)(?:me|le)? un pedido al proveedor "
            r"de (?P<quantity>\d+) (?P<product>.+?)(?: a precio (?P<price>\d+(?:[.,]\d+)?))?$",
            r"(?:haz|hacer|crea|crear|genera|generar|registra|registrar|pide|pedir)(?:me|le)? un pedido al proveedor "
            r"del producto (?P<product>.+?) por (?P<quantity>\d+) unidades?(?: a precio (?P<price>\d+(?:[.,]\d+)?))?$",
        ]
        for pattern in patterns:
            match = re.search(pattern, message)
            if not match:
                continue
            supplier = self._last_supplier_name()
            if not supplier:
                return {
                    "intent": "missing_data",
                    "reply": "No tengo un proveedor reciente en memoria. Indica el nombre del proveedor para crear el pedido.",
                }
            raw_product = re.sub(r"^(?:de\s+)?", "", match.group("product")).strip()
            product = display_name(raw_product)
            item = {
                    "product_name": product,
                    "product_search_keys": product_search_keys(raw_product),
                    "quantity": int(match.group("quantity")),
                }
            if match.group("price"):
                item["unit_price"] = decimal_value(match.group("price"))
            return {
                "intent": "create_purchase_order",
                "reply": f"Registro un pedido a {supplier}.",
                "data": {"supplier_name": supplier, "items": [item]},
            }
        return None
    
    def _parse_contextual_purchase_order_v3(self, message):
        patterns = [
            r"(?:creale|hazle|crea|haz|genera|registra|pide)(?: un)? pedido de (?P<quantity>\d+) (?P<product>.+)$",
            r"(?:creale|hazle)(?: un)? pedido al proveedor de (?P<quantity>\d+) (?P<product>.+)$",
        ]

        for pattern in patterns:
            match = re.search(pattern, message)
            if not match:
                continue

            supplier = self._last_supplier_name()
            if not supplier:
                return {
                    "intent": "missing_data",
                    "reply": "No tengo un proveedor reciente en memoria. Indica el nombre del proveedor para crear el pedido.",
                    "data": {},
                }

            raw_product = clean_text_field(match.group("product"))
            product = display_name(raw_product)

            return {
                "intent": "create_purchase_order",
                "reply": f"Registro un pedido a {supplier}.",
                "data": {
                    "supplier_name": supplier,
                    "items": [
                        {
                            "product_name": product,
                            "quantity": int(match.group("quantity")),
                            "product_search_keys": product_search_keys(raw_product),
                        }
                    ],
                },
            }

        return None

    def _parse_quick_inventory_add(self, message):
        match = re.search(
            r"(?:introduce|introducir|meter|agregar|anadir|añadir|sumar|registrar) (?P<name>.+?) "
            r"(?:en|al|a el)? ?inventario[, ]+(?P<stock>\d+)(?: unidades)?(?: concretamente)?$",
            message,
        )
        if not match:
            match = re.search(
                r"(?:introduce|introducir|meter|agregar|anadir|añadir|sumar|registrar) (?P<stock>\d+) "
                r"(?:unidades de )?(?P<name>.+?)(?: al inventario| en inventario)?$",
                message,
            )
        if not match:
            match = re.search(
                r"(?:mete|pon|carga) (?P<stock>\d+) (?P<name>.+?)(?: al inventario| en inventario)?$",
                message,
            )
        if not match:
            return None
        name = display_name(match.group("name"))
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
        if not re.search(r"\b(?:crea|crear|registra|registrar|agrega|agregar|anade|añade)\b.*\bproducto\b", message):
            return None

        name_match = re.search(
            r"producto(?:\s+llamado|\s+con nombre)?\s+(?P<name>.+?)(?=\s+(?:con\s+)?(?:stock|precio|categoria|descripcion|minimo|stock minimo)\b|,|$)",
            message,
        )

        stock = extract_int_after_keywords(message, ["stock", "cantidad"])
        price = extract_number_after_keywords(message, ["precio", "vale", "cuesta"])
        minimum_stock = extract_int_after_keywords(message, ["stock minimo", "minimo"])

        category_match = re.search(r"\bcategoria\s+(?P<category>.+?)(?=\s+(?:stock|precio|descripcion|minimo|stock minimo)\b|,|$)", message)
        description_match = re.search(r"\bdescripcion\s+(?P<description>.+?)(?=\s+(?:stock|precio|categoria|minimo|stock minimo)\b|,|$)", message)

        if not name_match:
            return {"intent": "missing_data", "reply": "Falta el nombre del producto.", "data": {}}

        missing = []
        if stock is None:
            missing.append("stock")
        if price is None:
            missing.append("precio")

        if missing:
            return {
                "intent": "missing_data",
                "reply": f"Faltan datos obligatorios para crear el producto: {', '.join(missing)}.",
                "data": {},
            }

        name = display_name(name_match.group("name"))

        return {
            "intent": "create_product",
            "reply": f"Creo el producto {name}.",
            "data": {
                "name": name,
                "stock": stock,
                "unit_price": price,
                "description": clean_text_field(description_match.group("description")) if description_match else "",
                "category": clean_text_field(category_match.group("category")) if category_match else "",
                "minimum_stock": minimum_stock or 0,
            },
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
        match = re.search(
            r"(?:confirma )?(?:elimina|eliminar|borra|borrar) "
            r"(?:(?P<quantity>\d+)(?: unidades?(?: de)?| uds?(?: de)?)?\s+)?"
            r"(?:el |la )?(?:producto |articulo |articulos )?(?P<name>.+)$",
            message,
        )
        if not match:
            return None
        raw_name = re.sub(r"^(?:de\s+)?(?:articulo|articulos)\s+", "", match.group("name")).strip()
        raw_name = re.sub(r"\s+(?:del|de|en)\s+inventario$", "", raw_name).strip()
        name = display_name(raw_name)
        if not name:
            return None
        if normalize_text(name) in ["todo", "todos", "toda", "inventario", "almacen", "productos"]:
            return None
        data = {"name": name}
        if match.group("quantity"):
            data["quantity"] = int(match.group("quantity"))
            reply = f"Descuento {data['quantity']} unidad(es) de {name}."
        else:
            reply = f"Elimino el producto {name}."
        return {"intent": "delete_product", "reply": reply, "data": data}

    def _parse_create_supplier(self, message):
        if not re.search(r"\b(?:registra|registrar|crea|crear|alta|dar de alta)\b.*\bproveedor\b", message):
            return None

        name_match = re.search(
            r"proveedor(?:\s+llamado|\s+con nombre)?\s+(?P<name>.+?)(?=\s+(?:con\s+)?(?:email|telefono|tlf|tel|direccion|cif)\b|,|$)",
            message,
        )

        email = extract_email(message)
        phone = extract_phone(message)
        cif = extract_cif(message)

        address_match = re.search(
            r"\bdireccion\s+(?P<address>.+?)(?=\s+(?:email|telefono|tlf|tel|cif)\b|,|$)",
            message,
        )

        if not name_match:
            return {"intent": "missing_data", "reply": "Falta el nombre del proveedor.", "data": {}}

        if not email:
            return {
                "intent": "missing_data",
                "reply": "Falta el email del proveedor. Ejemplo: registra un proveedor llamado ClimaSur con email contacto@climasur.com.",
                "data": {},
            }

        name = display_name(name_match.group("name"))

        data = {
            "name": name,
            "contact_email": email,
            "phone": phone,
            "address": clean_text_field(address_match.group("address")) if address_match else "",
            "products_supplied": [],
        }

        if cif:
            data["cif"] = cif

        return {
            "intent": "create_supplier",
            "reply": f"Registro el proveedor {name}.",
            "data": data,
        }
    
    def _parse_update_supplier_phone_direct(self, message):
        match = re.search(
            r"(?:actualiza|actualizar|cambia|cambiar|modifica|modificar) "
            r"(?:el )?telefono (?:de|del proveedor) (?P<name>.+?) a (?P<phone>[\d+ ]+)$",
            message,
        )
        if not match:
            return None

        name = display_name(match.group("name"))
        phone = clean_text_field(match.group("phone"))

        return {
            "intent": "update_supplier",
            "reply": f"Actualizo el teléfono del proveedor {name}.",
            "data": {
                "name": name,
                "phone": phone,
            },
        }

    def _parse_update_supplier(self, message):
        if not re.search(r"\b(?:actualiza|actualizar|modifica|modificar|cambia|cambiar)\b.*\bproveedor\b", message):
            return None

        name_match = re.search(
            r"proveedor\s+(?P<name>.+?)(?=\s+(?:con\s+)?(?:nombre|email|telefono|tlf|tel|direccion|cif)\b|,|$)",
            message,
        )

        if not name_match:
            return {"intent": "missing_data", "reply": "Indica qué proveedor quieres actualizar.", "data": {}}

        data = {"name": display_name(name_match.group("name"))}

        new_name_match = re.search(r"\bnombre\s+(?P<new_name>.+?)(?=\s+(?:email|telefono|tlf|tel|direccion|cif)\b|,|$)", message)
        email = extract_email(message)
        phone = extract_phone(message)
        cif = extract_cif(message)
        address_match = re.search(r"\bdireccion\s+(?P<address>.+?)(?=\s+(?:email|telefono|tlf|tel|cif)\b|,|$)", message)

        if new_name_match:
            data["new_name"] = display_name(new_name_match.group("new_name"))
        if email:
            data["contact_email"] = email
        if phone:
            data["phone"] = phone
        if address_match:
            data["address"] = clean_text_field(address_match.group("address"))
        if cif:
            data["cif"] = cif

        if len(data) == 1:
            return {
                "intent": "missing_data",
                "reply": "Indica al menos un campo para actualizar el proveedor, por ejemplo email, teléfono, dirección, CIF o nombre.",
                "data": {},
            }

        return {"intent": "update_supplier", "reply": f"Actualizo el proveedor {data['name']}.", "data": data}

    def _parse_delete_supplier(self, message):
        match = re.search(r"(?:confirma )?(?:elimina|eliminar|borra|borrar) (?:el )?proveedor (?P<name>.+)$", message)
        if not match:
            return None
        name = display_name(match.group("name"))
        return {"intent": "delete_supplier", "reply": f"Elimino el proveedor {name}.", "data": {"name": name}}
    
    def _parse_pending_product_selection(self, message):
        pending = (self._context or {}).get("pending_action")

        if not pending:
            return None

        if pending.get("intent") not in {"create_purchase_order", "add_product_stock"}:
            return None

        selection_prefix = re.match(r"^(?:quiero usar|usar|usa|elijo|selecciono)\s+", message)
        if looks_like_new_command(message) and not selection_prefix:
            return None

        selected_product = re.sub(r"^(?:quiero usar|usar|usa|elijo|selecciono)\s+", "", message).strip()

        if not selected_product:
            return None

        if pending.get("intent") == "add_product_stock":
            quantity = pending.get("quantity")
            if quantity is None:
                return None
            return {
                "intent": "add_product_stock",
                "reply": f"Registro {quantity} unidades de {display_name(selected_product)} en el inventario.",
                "data": {
                    "name": display_name(selected_product),
                    "quantity": int(quantity),
                    "resolved_from_pending_selection": True,
                },
            }

        pending_items = pending.get("items") or []
        if not pending_items:
            return None

        base_item = dict(pending_items[0])
        base_item["product_name"] = display_name(selected_product)
        base_item["product_search_keys"] = product_search_keys(selected_product)

        return {
            "intent": "create_purchase_order",
            "reply": f"Registro el pedido usando {display_name(selected_product)}.",
            "data": {
                "supplier_name": pending.get("supplier_name"),
                "items": [base_item],
                "resolved_from_pending_selection": True,
            },
        }

    def _parse_pending_duplicate_update(self, message):
        pending = (self._context or {}).get("pending_action")
        if not pending:
            return None

        normalized_message = normalize_text(message).strip()
        if normalized_message not in {"actualiza", "actualizar", "actualizalo", "actualizala", "si actualiza"}:
            return None

        if pending.get("intent") == "duplicate_create_product":
            update_data = dict(pending.get("update_data") or {})
            if not update_data.get("name"):
                return None
            return {
                "intent": "update_product",
                "reply": f"Actualizo el producto {update_data['name']}.",
                "data": update_data,
            }

        if pending.get("intent") == "duplicate_create_supplier":
            update_data = dict(pending.get("update_data") or {})
            if not update_data.get("name"):
                return None
            return {
                "intent": "update_supplier",
                "reply": f"Actualizo el proveedor {update_data['name']}.",
                "data": update_data,
            }

        return None

    def _parse_supplier_details(self, message):
        match = re.search(
            r"(?:dame|muestrame|mostrar|ver|consulta).*datos.*(?:de|del proveedor) (?P<name>.+)$",
            message,
        )
        if not match:
            return None

        return {
            "intent": "list_suppliers",
            "reply": f"Consulto los datos del proveedor {display_name(match.group('name'))}.",
            "data": {"name": display_name(match.group("name"))},
        }

    def _parse_create_purchase_order(self, message):
        patterns = [
            r"(?:crea|crear|registra|registrar)(?:me)? un pedido al proveedor (?P<supplier>.+?) "
            r"de (?P<quantity>\d+) (?:unidades?(?: de)? )?(?P<product>.+?)(?: a precio (?P<price>\d+(?:[.,]\d+)?))?$",
            r"(?:haz|hacer|crea|crear|registra|registrar)(?:me)? un pedido a (?P<supplier>.+?) "
            r"de (?P<quantity>\d+) (?:unidades?(?: de)? )?(?P<product>.+?)(?: a precio (?P<price>\d+(?:[.,]\d+)?))?$",
            r"(?:pide|pedir)(?:me)? a (?P<supplier>.+?) "
            r"(?P<quantity>\d+) (?:unidades?(?: de)? )?(?P<product>.+?)(?: a precio (?P<price>\d+(?:[.,]\d+)?))?$",
        ]
        for pattern in patterns:
            match = re.search(pattern, message)
            if not match:
                continue
            supplier = display_name(match.group("supplier"))
            raw_product = clean_text_field(match.group("product"))
            product = display_name(raw_product)
            item = {"product_name": product, 
                    "product_search_keys": product_search_keys(raw_product),
                    "quantity": int(match.group("quantity"))}
            if match.group("price"):
                item["unit_price"] = decimal_value(match.group("price"))
            return {
                "intent": "create_purchase_order",
                "reply": f"Registro un pedido a {supplier}.",
                "data": {"supplier_name": supplier, "items": [item]},
            }
        return None

        
    def _parse_contextual_purchase_order(self, message):
        match = re.search(
            r"(?:haz|hacer|crea|crear|registra|registrar|pide|pedir)(?:me|le)? un pedido "
            r"de (?P<quantity>\d+) unidades de (?P<product>.+?)(?: a precio (?P<price>\d+(?:[.,]\d+)?))?$",
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

        raw_product = clean_text_field(match.group("product"))
        product = display_name(raw_product)
        item = {"product_name": product, 
                "product_search_keys": product_search_keys(raw_product),
                "quantity": int(match.group("quantity"))}
        if match.group("price"):
            item["unit_price"] = decimal_value(match.group("price"))

        return {
            "intent": "create_purchase_order",
            "reply": f"Registro un pedido a {supplier}.",
            "data": {"supplier_name": supplier, "items": [item]},
        }

    def _parse_receive_purchase_order(self, message):
        partial_match = re.search(
            r"(?:hemos )?(?:recibido|recibimos|llego|ha llegado) (?P<quantity>\d+) unidades de (?P<product>.+?) "
            r"del pedido (?:del |de )?proveedor (?P<supplier>.+)$",
            message,
        )
        
        if partial_match:
            raw_product = clean_text_field(partial_match.group("product"))
            supplier = display_name(partial_match.group("supplier"))
            return {
                "intent": "receive_purchase_order",
                "reply": f"Registro una recepción parcial del pedido de {supplier}.",
                "data": {
                    "supplier_name": supplier,
                    "items": [
                        {
                            "product_name": display_name(raw_product),
                            "product_search_keys": product_search_keys(raw_product),
                            "quantity": int(partial_match.group("quantity")),
                        }
                    ],
                },
            }

        match = re.search(
            r"(?:hemos )?(?:recibido|recibimos|llego|ha llegado) (?:el )?pedido (?:del |de )?proveedor (?P<supplier>.+)$",
            message,
        )
        if match:
            supplier = display_name(match.group("supplier"))
            return {
                "intent": "receive_purchase_order",
                "reply": f"Marco como recibido el último pedido pendiente de {supplier}.",
                "data": {"supplier_name": supplier},
            }

        match = re.search(
            r"(?:hemos )?(?:recibido|recibimos|llego|ha llegado) (?:el )?pedido (?P<id>[a-f0-9]{24})$",
            message,
        )
        if match:
            return {
                "intent": "receive_purchase_order",
                "reply": "Marco como recibido el pedido indicado.",
                "data": {"id": clean_identifier(match.group("id"))},
            }
        return None

    def _parse_cancel_purchase_order(self, message):
        match = re.search(
            r"(?:cancela|cancelar|anula|anular) (?:el )?pedido (?:del |de )?proveedor (?P<supplier>.+?)(?: por (?P<reason>.+))?$",
            message,
        )
        if match:
            data = {"supplier_name": display_name(match.group("supplier"))}
            if match.group("reason"):
                data["reason"] = match.group("reason").strip()
            return {
                "intent": "cancel_purchase_order",
                "reply": f"Cancelo el último pedido abierto de {data['supplier_name']}.",
                "data": data,
            }

        match = re.search(
            r"(?:cancela|cancelar|anula|anular) (?:el )?pedido (?P<id>[a-f0-9]{24})(?: por (?P<reason>.+))?$",
            message,
        )
        if match:
            data = {"id": clean_identifier(match.group("id"))}
            if match.group("reason"):
                data["reason"] = match.group("reason").strip()
            return {
                "intent": "cancel_purchase_order",
                "reply": "Cancelo el pedido indicado.",
                "data": data,
            }
        return None

    def _parse_update_purchase_order(self, message):
        match = re.search(
            r"(?:actualiza|actualizar|modifica|modificar) (?:el )?pedido (?P<id>[a-f0-9]{24}) "
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

    def _parse_delete_purchase_order(self, message):
        match = re.search(r"(?:confirma )?(?:elimina|eliminar|borra|borrar) (?:el )?pedido (?P<id>[a-f0-9]{24})", message)
        if not match:
            return None
        return {"intent": "delete_purchase_order", "reply": "Elimino el pedido indicado.", "data": {"id": clean_identifier(match.group("id"))}}

    def _parse_delete_all_purchase_orders(self, message):
        if not any(term in message for term in ["elimina", "eliminar", "borra", "borrar"]):
            return None
        if not ("pedido" in message and any(term in message for term in ["todo", "todos", "registrados"])):
            return None
        return {
            "intent": "confirmation_required",
            "reply": "Esta accion eliminara todos los pedidos registrados. Quieres continuar? Responde si o no.",
            "data": {
                "pending_action": "delete_all_purchase_orders",
                "confirmation_token": confirmation_token(
                    "delete_all_purchase_orders",
                    "Elimino todos los pedidos registrados.",
                    {},
                ),
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

    def _parse_create_waste(self, message):
        match = re.search(
            r"(?:registra|registrar|crea|crear) un desecho de (?P<quantity>\d+) unidades de (?P<product>.+?) "
            r"por (?P<reason>caducidad|producto danado|ajuste manual)$",
            message,
        )
        if not match:
            return None
        reason = match.group("reason").replace("danado", "dañado")
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
            r"(?:actualiza|actualizar|modifica|modificar) (?:el )?desecho (?P<id>[a-f0-9]{24}) "
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
        match = re.search(r"(?:confirma )?(?:elimina|eliminar|borra|borrar) (?:el )?desecho (?P<id>[a-f0-9]{24})", message)
        if not match:
            return None
        return {"intent": "delete_waste", "reply": "Elimino el desecho indicado.", "data": {"id": clean_identifier(match.group("id"))}}

    def _parse_delete_all_suppliers(self, message):
        if not any(term in message for term in ["elimina", "eliminar", "borra", "borrar"]):
            return None
        if not ("proveedor" in message and any(term in message for term in ["todo", "todos", "registrados"])):
            return None
        return {
            "intent": "confirmation_required",
            "reply": "Esta accion eliminara todos los proveedores. Quieres continuar? Responde si o no.",
            "data": {"pending_action": "delete_all_suppliers", "confirmation_token": confirmation_token("delete_all_suppliers", "Elimino todos los proveedores.", {})},
        }

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
        contextual_message = build_contextual_user_message(user_message, context)
        payload = {
            "model": model,
            "instructions": SYSTEM_PROMPT,
            "input": contextual_message,
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
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        contextual_message = build_contextual_user_message(user_message, context)
        structured_payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": contextual_message}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": RESPONSE_SCHEMA,
                "temperature": 0.1,
                "maxOutputTokens": 450,
            },
        }
        relaxed_payload = {
            "system_instruction": {
                "parts": [
                    {
                        "text": (
                            f"{SYSTEM_PROMPT}\n\n"
                            "Responde solo con JSON válido, sin markdown ni explicaciones extra."
                        )
                    }
                ]
            },
            "contents": [{"parts": [{"text": contextual_message}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1,
                "maxOutputTokens": 450,
            },
        }
        try:
            last_error = None
            for payload in [structured_payload, relaxed_payload]:
                try:
                    response = requests.post(
                        url,
                        headers={"Content-Type": "application/json"},
                        json=payload,
                        timeout=25,
                    )
                    response.raise_for_status()
                    body = response.json()
                    text = _gemini_output_text(body)
                    result = normalize_llm_result(extract_json_object(text))
                    result["provider_status"] = f"API real: {model}"
                    return result
                except Exception as exc:
                    last_error = exc
            raise last_error or RuntimeError("Gemini no devolvió una respuesta útil.")
        except Exception as exc:
            return fallback_result("Gemini", user_message, context, f"error Gemini: {exc}")


class ClaudeProvider(BaseLLMProvider):
    name = "claude"

    def generate_response(self, user_message, context):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return fallback_result("Claude", user_message, context, "sin clave Claude")

        model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
        contextual_message = build_contextual_user_message(user_message, context)
        payload = {
            "model": model,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": contextual_message}],
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
        local_url = os.getenv("LOCAL_LLM_URL")
        if not local_url:
            result = MockLLMProvider().generate_response(user_message, context)
            result["reply"] = f"{result['reply']} (simulado sin modelo local)."
            return result

        model = os.getenv("LOCAL_LLM_MODEL", "llama3.1:8b")
        contextual_message = build_contextual_user_message(user_message, context)
        payload = {
            "model": model,
            "system": SYSTEM_PROMPT,
            "prompt": contextual_message,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1},
        }
        try:
            response = requests.post(
                f"{local_url.rstrip('/')}/api/generate",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=25,
            )
            response.raise_for_status()
            body = response.json()
            text = body.get("response", "")
            result = normalize_llm_result(extract_json_object(text))
            result["provider_status"] = f"API local: {model}"
            return result
        except Exception as exc:
            return fallback_result("Local", user_message, context, f"error local: {exc}")


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


def _gemini_output_text(body):
    chunks = []
    for candidate in body.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            if part.get("text"):
                chunks.append(part["text"])
    return "".join(chunks)
