import os
import re


class BaseLLMProvider:
    name = "base"

    def generate_response(self, user_message, context):
        raise NotImplementedError


class MockLLMProvider(BaseLLMProvider):
    name = "mock"

    def generate_response(self, user_message, context):
        message = user_message.strip()
        lowered = message.lower()

        if "muestrame" in lowered or "muéstrame" in lowered or "lista" in lowered:
            if "producto" in lowered:
                return {"intent": "list_products", "reply": "Voy a mostrar los productos."}
            if "proveedor" in lowered:
                return {"intent": "list_suppliers", "reply": "Voy a mostrar los proveedores."}
            if "estad" in lowered or "perdidas" in lowered or "pérdidas" in lowered:
                return {"intent": "show_statistics", "reply": "Voy a consultar las estadísticas."}

        create_product_match = re.search(
            r"crea(?:r)? un producto llamado (?P<name>.+?)(?: con stock (?P<stock>\d+))?(?: y precio (?P<price>\d+(?:[.,]\d+)?))?",
            lowered,
        )
        if create_product_match:
            name = create_product_match.group("name")
            return {
                "intent": "create_product",
                "reply": f"Voy a crear el producto {name.title()}.",
                "data": {
                    "name": name.title(),
                    "stock": int(create_product_match.group("stock") or 0),
                    "unit_price": float((create_product_match.group("price") or "0").replace(",", ".")),
                    "description": "",
                    "category": "",
                    "minimum_stock": 0,
                },
            }

        update_product_match = re.search(
            r"actualiza(?:r)? el producto (?P<name>.+?)(?: con stock (?P<stock>\d+))?(?: y precio (?P<price>\d+(?:[.,]\d+)?))?$",
            lowered,
        )
        if update_product_match:
            data = {"name": update_product_match.group("name").title()}
            if update_product_match.group("stock"):
                data["stock"] = int(update_product_match.group("stock"))
            if update_product_match.group("price"):
                data["unit_price"] = float(update_product_match.group("price").replace(",", "."))
            return {
                "intent": "update_product",
                "reply": f"Voy a actualizar el producto {data['name']}.",
                "data": data,
            }

        delete_product_match = re.search(r"elimina(?:r)? el producto (?P<name>.+)$", lowered)
        if delete_product_match:
            return {
                "intent": "delete_product",
                "reply": f"Voy a eliminar el producto {delete_product_match.group('name').title()}.",
                "data": {"name": delete_product_match.group("name").title()},
            }

        create_supplier_match = re.search(
            r"(?:registra|crea)(?:r)? un proveedor llamado (?P<name>.+?)(?: con email (?P<email>\S+))?$",
            lowered,
        )
        if create_supplier_match:
            return {
                "intent": "create_supplier",
                "reply": f"Voy a registrar el proveedor {create_supplier_match.group('name').title()}.",
                "data": {
                    "name": create_supplier_match.group("name").title(),
                    "contact_email": create_supplier_match.group("email") or "proveedor@example.com",
                    "phone": "",
                    "address": "",
                    "products_supplied": [],
                },
            }

        purchase_order_match = re.search(
            r"crea(?:r)? un pedido al proveedor (?P<supplier>.+?) de (?P<quantity>\d+) unidades de (?P<product>.+)$",
            lowered,
        )
        if purchase_order_match:
            return {
                "intent": "create_purchase_order",
                "reply": f"Voy a registrar un pedido a {purchase_order_match.group('supplier').title()}.",
                "data": {
                    "supplier_name": purchase_order_match.group("supplier").title(),
                    "items": [
                        {
                            "product_name": purchase_order_match.group("product").title(),
                            "quantity": int(purchase_order_match.group("quantity")),
                        }
                    ],
                },
            }

        waste_match = re.search(
            r"registra(?:r)? un desecho de (?P<quantity>\d+) unidades de (?P<product>.+?) por (?P<reason>caducidad|producto dañado|ajuste manual)$",
            lowered,
        )
        if waste_match:
            return {
                "intent": "create_waste",
                "reply": f"Voy a registrar el desecho de {waste_match.group('product').title()}.",
                "data": {
                    "product_name": waste_match.group("product").title(),
                    "quantity": int(waste_match.group("quantity")),
                    "reason": waste_match.group("reason"),
                },
            }

        if "estad" in lowered or "perdidas" in lowered or "pérdidas" in lowered:
            return {"intent": "show_statistics", "reply": "Voy a consultar las estadísticas."}

        return {
            "intent": "fallback",
            "reply": "No he identificado una acción exacta. Puedes pedirme listar productos, crear proveedores, registrar pedidos o consultar estadísticas.",
        }


class OpenAIProvider(BaseLLMProvider):
    name = "openai"

    def generate_response(self, user_message, context):
        if not os.getenv("OPENAI_API_KEY"):
            return MockLLMProvider().generate_response(user_message, context)
        return {
            "intent": "fallback",
            "reply": "Proveedor OpenAI preparado. Añade la llamada real a la API para comparar respuestas avanzadas.",
        }


class GeminiProvider(BaseLLMProvider):
    name = "gemini"

    def generate_response(self, user_message, context):
        if not os.getenv("GEMINI_API_KEY"):
            return MockLLMProvider().generate_response(user_message, context)
        return {
            "intent": "fallback",
            "reply": "Proveedor Gemini preparado. Añade la llamada real a la API para comparar respuestas avanzadas.",
        }


class LocalLLMProvider(BaseLLMProvider):
    name = "local"

    def generate_response(self, user_message, context):
        if not os.getenv("LOCAL_LLM_URL"):
            return MockLLMProvider().generate_response(user_message, context)
        return {
            "intent": "fallback",
            "reply": "Proveedor local preparado. Conecta aquí tu modelo local para pruebas comparativas.",
        }


def get_provider(provider_name=None):
    selected = (provider_name or os.getenv("DEFAULT_LLM_PROVIDER", "mock")).lower()
    providers = {
        "mock": MockLLMProvider(),
        "openai": OpenAIProvider(),
        "gemini": GeminiProvider(),
        "local": LocalLLMProvider(),
    }
    return providers.get(selected, providers["mock"])
