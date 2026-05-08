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
    "update_product",
    "delete_product",
    "list_suppliers",
    "create_supplier",
    "update_supplier",
    "delete_supplier",
    "list_purchase_orders",
    "create_purchase_order",
    "update_purchase_order",
    "delete_purchase_order",
    "list_waste",
    "create_waste",
    "update_waste",
    "delete_waste",
    "show_statistics",
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


SYSTEM_PROMPT = """
Eres el clasificador de intenciones de un prototipo ERP conversacional.
Tu unica salida debe ser JSON valido con esta forma:
{"intent": "...", "reply": "...", "data": {...}}

No ejecutes operaciones por tu cuenta. Solo interpreta el mensaje del usuario.
El backend ejecutara la operacion indicada.

Intenciones permitidas:
- help
- confirmation_required
- missing_data
- fallback
- list_products, create_product, update_product, delete_product
- list_suppliers, create_supplier, update_supplier, delete_supplier
- list_purchase_orders, create_purchase_order, update_purchase_order, delete_purchase_order
- list_waste, create_waste, update_waste, delete_waste
- show_statistics

Reglas de seguridad:
- Para eliminar productos, proveedores, pedidos o desechos, si el mensaje no empieza con "confirma",
  usa confirmation_required.
- Si faltan campos obligatorios, usa missing_data.
- Si la intencion no es clara, usa fallback.

Campos esperados por intencion:
- create_product: data.name, data.stock, data.unit_price. Opcionales: description, category, minimum_stock.
- update_product: data.name y al menos uno de new_name, stock, unit_price, category, minimum_stock.
- delete_product: data.name.
- create_supplier: data.name, data.contact_email. Opcionales: phone, address, products_supplied.
- update_supplier: data.name y al menos uno de new_name, contact_email, phone, address.
- delete_supplier: data.name.
- create_purchase_order: data.supplier_name, data.items. Cada item necesita product_name y quantity. unit_price opcional.
- update_purchase_order: data.id, data.supplier_name, data.items. status opcional.
- delete_purchase_order: data.id.
- create_waste: data.product_name, data.quantity, data.reason. reason debe ser caducidad, producto dañado o ajuste manual.
- update_waste: data.id, data.product_name, data.quantity, data.reason.
- delete_waste: data.id.
- list_* y show_statistics: data debe ser {}.

Normaliza nombres propios de productos y proveedores con mayusculas profesionales.
Responde siempre en espanol profesional y breve.
""".strip()


class BaseLLMProvider:
    name = "base"

    def generate_response(self, user_message, context):
        raise NotImplementedError


def normalize_text(value):
    value = unicodedata.normalize("NFD", value.strip().lower())
    return "".join(char for char in value if unicodedata.category(char) != "Mn")


def display_name(value):
    acronyms = {"api", "erp", "hepa", "llm", "sku"}
    return " ".join(word.upper() if word in acronyms else word.capitalize() for word in value.strip().split())


def decimal_value(value, default=0):
    if value is None:
        return default
    return float(value.replace(",", "."))


def clean_identifier(value):
    return value.strip().strip(".:,;")


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


class MockLLMProvider(BaseLLMProvider):
    name = "mock"

    def generate_response(self, user_message, context):
        raw_message = user_message.strip()
        lowered = normalize_text(raw_message)

        if self._is_statistics_request(lowered):
            return {"intent": "show_statistics", "reply": "Consulto las estadísticas del ERP."}

        if self._is_help_request(lowered):
            return {
                "intent": "help",
                "reply": (
                    "Puedo operar el ERP por lenguaje natural. Ejemplos: "
                    "lista productos; crea un producto llamado Filtro HEPA con stock 20 y precio 35; "
                    "actualiza el producto Filtro HEPA con stock 30 y precio 40; "
                    "registra un proveedor llamado ClimaSur con email contacto@climasur.com; "
                    "crea un pedido al proveedor ClimaSur de 10 unidades de Filtro HEPA; "
                    "registra un desecho de 3 unidades de Filtro HEPA por caducidad; "
                    "muestrame estadisticas. Para borrar, escribe confirma eliminar ..."
                ),
            }

        if self._is_delete_without_confirmation(lowered):
            return {
                "intent": "confirmation_required",
                "reply": "Para evitar bajas accidentales, confirma la operación escribiendo: confirma eliminar ...",
            }

        list_intent = self._list_intent(lowered)
        if list_intent:
            return {"intent": list_intent, "reply": "Consulto la información solicitada."}

        for parser in [
            self._parse_create_product,
            self._parse_update_product,
            self._parse_delete_product,
            self._parse_create_supplier,
            self._parse_update_supplier,
            self._parse_delete_supplier,
            self._parse_create_purchase_order,
            self._parse_update_purchase_order,
            self._parse_delete_purchase_order,
            self._parse_create_waste,
            self._parse_update_waste,
            self._parse_delete_waste,
        ]:
            parsed = parser(lowered)
            if parsed:
                return parsed

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
        return message in ["ayuda", "help", "comandos", "que puedo hacer"] or "como uso" in message

    def _is_delete_without_confirmation(self, message):
        return (
            any(term in message for term in ["elimina", "eliminar", "borra", "borrar"])
            and not message.startswith("confirma ")
        )

    def _list_intent(self, message):
        if not any(term in message for term in ["muestrame", "mostrar", "lista", "listar", "ver", "consulta"]):
            return None
        if "producto" in message:
            return "list_products"
        if "proveedor" in message:
            return "list_suppliers"
        if "pedido" in message or "orden" in message:
            return "list_purchase_orders"
        if "desecho" in message or "merma" in message:
            return "list_waste"
        return None

    def _parse_create_product(self, message):
        match = re.search(
            r"(?:crea|crear|registra|registrar) un producto llamado (?P<name>.+?)"
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
        match = re.search(r"confirma (?:elimina|eliminar|borra|borrar) (?:el )?producto (?P<name>.+)$", message)
        if not match:
            return None
        name = display_name(match.group("name"))
        return {"intent": "delete_product", "reply": f"Elimino el producto {name}.", "data": {"name": name}}

    def _parse_create_supplier(self, message):
        match = re.search(
            r"(?:registra|registrar|crea|crear) un proveedor llamado (?P<name>.+?)"
            r"(?: con email (?P<email>\S+))?"
            r"(?: y telefono (?P<phone>[\d+ ]+))?"
            r"(?: y direccion (?P<address>.+))?$",
            message,
        )
        if not match:
            return None
        if not match.group("email"):
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
                "contact_email": match.group("email") or "proveedor@example.com",
                "phone": (match.group("phone") or "").strip(),
                "address": match.group("address") or "",
                "products_supplied": [],
            },
        }

    def _parse_update_supplier(self, message):
        match = re.search(
            r"(?:actualiza|actualizar|modifica|modificar) (?:el )?proveedor (?P<name>.+?)"
            r"(?: con nombre (?P<new_name>.+?))?"
            r"(?: con email (?P<email>\S+))?"
            r"(?: y telefono (?P<phone>[\d+ ]+))?"
            r"(?: y direccion (?P<address>.+))?$",
            message,
        )
        if not match:
            return None
        data = {"name": display_name(match.group("name"))}
        if match.group("new_name"):
            data["new_name"] = display_name(match.group("new_name"))
        if match.group("email"):
            data["contact_email"] = match.group("email")
        if match.group("phone"):
            data["phone"] = match.group("phone").strip()
        if match.group("address"):
            data["address"] = match.group("address")
        if len(data) == 1:
            return {
                "intent": "missing_data",
                "reply": "Indica al menos un campo para actualizar el proveedor, por ejemplo email, teléfono, dirección o nombre.",
            }
        return {"intent": "update_supplier", "reply": f"Actualizo el proveedor {data['name']}.", "data": data}

    def _parse_delete_supplier(self, message):
        match = re.search(r"confirma (?:elimina|eliminar|borra|borrar) (?:el )?proveedor (?P<name>.+)$", message)
        if not match:
            return None
        name = display_name(match.group("name"))
        return {"intent": "delete_supplier", "reply": f"Elimino el proveedor {name}.", "data": {"name": name}}

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
        match = re.search(r"confirma (?:elimina|eliminar|borra|borrar) (?:el )?pedido (?P<id>[a-f0-9]{24})", message)
        if not match:
            return None
        return {"intent": "delete_purchase_order", "reply": "Elimino el pedido indicado.", "data": {"id": clean_identifier(match.group("id"))}}

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
        match = re.search(r"confirma (?:elimina|eliminar|borra|borrar) (?:el )?desecho (?P<id>[a-f0-9]{24})", message)
        if not match:
            return None
        return {"intent": "delete_waste", "reply": "Elimino el desecho indicado.", "data": {"id": clean_identifier(match.group("id"))}}


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

    def generate_response(self, user_message, context):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return fallback_result("Gemini", user_message, context, "sin clave Gemini")

        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
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
    providers = {
        "mock": MockLLMProvider(),
        "openai": OpenAIProvider(),
        "gemini": GeminiProvider(),
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
