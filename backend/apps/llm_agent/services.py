from mongoengine.errors import DoesNotExist, NotUniqueError, ValidationError

from apps.audit.services import (
    deleted_products_history,
    record_audit,
    serialize_audit_entry,
    supplier_audit_history,
)
from apps.llm_agent.providers import confirmation_token, get_provider, parse_confirmation_token
from apps.products.services import (
    clear_products_inventory,
    create_product,
    delete_product,
    get_product_document_by_name,
    list_products,
    product_insights,
    update_product,
)
from apps.purchase_orders.domain import PurchaseOrderDomainError
from apps.purchase_orders.services import (
    append_items_to_purchase_order,
    cancel_latest_purchase_order,
    cancel_purchase_order,
    create_purchase_order,
    delete_purchase_order,
    list_purchase_orders,
    mark_purchase_order_completed,
    order_insights,
    receive_latest_purchase_order_for_supplier,
    receive_purchase_order,
    update_purchase_order,
)
from apps.statistics.services import statistics_overview
from apps.suppliers.services import (
    clear_suppliers,
    create_supplier,
    delete_supplier,
    get_supplier_document_by_name,
    list_suppliers,
    serialize_supplier,
    update_supplier,
)
from apps.suppliers.models import Supplier
from apps.waste.services import (
    clear_waste_records,
    create_waste_record,
    delete_waste_record,
    list_waste_records,
    process_expired_products,
    update_waste_record,
)
from common.observability import ObservedOperation, increment_metric


# Academic prototype note: this shared in-memory context keeps the demo simple for
# a single conversational flow. In a production ERP, user identity, permissions,
# and per-user/per-session state should be introduced so this memory is isolated
# and this approach replaced accordingly.
CONVERSATION_MEMORY = {
    "last_supplier_name": None,
    "last_product_name": None,
    "last_purchase_order_id": None,
    "pending_action": None,
    "auto_replenishment_enabled": False,
    "auto_replenishment_threshold": None,
}


def get_conversation_context():
    return {
        "last_supplier_name": CONVERSATION_MEMORY.get("last_supplier_name"),
        "last_product_name": CONVERSATION_MEMORY.get("last_product_name"),
        "last_purchase_order_id": CONVERSATION_MEMORY.get("last_purchase_order_id"),
        "pending_action": CONVERSATION_MEMORY.get("pending_action"),
        "auto_replenishment_enabled": CONVERSATION_MEMORY.get("auto_replenishment_enabled", False),
        "auto_replenishment_threshold": CONVERSATION_MEMORY.get("auto_replenishment_threshold"),
    }


def remember_supplier_name(supplier_name):
    if supplier_name:
        CONVERSATION_MEMORY["last_supplier_name"] = supplier_name


def remember_product_name(product_name):
    if product_name:
        CONVERSATION_MEMORY["last_product_name"] = product_name


def remember_purchase_order_id(order_id):
    if order_id:
        CONVERSATION_MEMORY["last_purchase_order_id"] = order_id


def remember_pending_action(pending_action):
    CONVERSATION_MEMORY["pending_action"] = pending_action


def clear_pending_action():
    CONVERSATION_MEMORY["pending_action"] = None


def set_auto_replenishment(enabled, threshold=None):
    CONVERSATION_MEMORY["auto_replenishment_enabled"] = bool(enabled)
    if threshold is None:
        CONVERSATION_MEMORY["auto_replenishment_threshold"] = None
    else:
        CONVERSATION_MEMORY["auto_replenishment_threshold"] = int(threshold)


def normalize_action_message(message):
    return (
        message.lower()
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("Á", "a")
        .replace("É", "e")
        .replace("Í", "i")
        .replace("Ó", "o")
        .replace("Ú", "u")
    )


def confirmation_prompt_for(intent, data):
    if intent == "delete_supplier":
        return f"Vas a eliminar el proveedor {data['name']}. Quieres continuar? Responde si o no."
    if intent == "update_purchase_order":
        return "Vas a modificar un pedido ya registrado. Quieres aplicar los cambios? Responde si o no."
    if intent == "delete_purchase_order":
        return "Vas a eliminar un pedido y ajustar el stock asociado. Quieres continuar? Responde si o no."
    if intent == "cancel_purchase_order":
        return "Vas a cancelar un pedido abierto. Quieres continuar? Responde si o no."
    if intent == "delete_all_products":
        return "Esta accion eliminara todo el inventario de productos. Quieres eliminarlo? Responde si o no."
    if intent == "delete_all_suppliers":
        return "Esta accion eliminara todos los proveedores sin pedidos asociados. Quieres continuar? Responde si o no."
    if intent == "delete_all_waste":
        return "Esta accion eliminara todos los desechos registrados. Quieres continuar? Responde si o no."
    return "La accion solicitada requiere confirmacion. Quieres continuar? Responde si o no."


def maybe_require_confirmation(message, result):
    intent = result.get("intent")
    result_data = result.get("data", {}) or {}
    sensitive_intents = {
        "delete_supplier",
        "update_purchase_order",
        "delete_purchase_order",
        "cancel_purchase_order",
        "delete_all_products",
        "delete_all_suppliers",
        "delete_all_waste",
    }
    if intent not in sensitive_intents:
        return None
    if intent == "update_purchase_order" and result_data.get("append_items"):
        return None
    if result.get("confirmed"):
        return None

    normalized_message = normalize_action_message(message).strip()
    if normalized_message.startswith("confirma "):
        return None

    return {
        "success": False,
        "provider": "assistant",
        "action": "confirmation_required",
        "reply": confirmation_prompt_for(intent, result.get("data", {})),
        "data": {
            "pending_action": intent,
            "confirmation_token": confirmation_token(intent, result.get("reply"), result_data),
        },
        "provider_status": None,
    }


def low_stock_note(product_name, stock, minimum_stock):
    if minimum_stock is None or minimum_stock <= 0:
        return None
    if stock >= minimum_stock:
        return None
    return (
        f" Este producto ha quedado por debajo del stock minimo ({stock}/{minimum_stock}). "
        "Quieres generar un pedido?"
    )


def proactive_note_for(action, data):
    if not isinstance(data, dict):
        return None

    if {"name", "stock", "minimum_stock"}.issubset(data.keys()):
        return low_stock_note(data["name"], data["stock"], data["minimum_stock"])

    if {"product_name", "remaining_stock", "minimum_stock"}.issubset(data.keys()):
        return low_stock_note(data["product_name"], data["remaining_stock"], data["minimum_stock"])

    if action == "get_product_stock":
        return low_stock_note(data.get("name"), data.get("stock"), data.get("minimum_stock"))

    product_names = []
    if action == "update_purchase_order":
        product_names = [item.get("product_name") for item in data.get("items", []) if item.get("product_name")]
    elif action == "delete_purchase_order":
        product_names = [item.get("product_name") for item in data.get("affected_products", []) if item.get("product_name")]

    for product_name in product_names:
        try:
            product = get_product_document_by_name(product_name)
        except Exception:
            continue
        note = low_stock_note(product.name, product.stock, product.minimum_stock)
        if note:
            return note

    return None


def find_supplier_for_product(product_name):
    normalized = normalize_action_message(product_name or "")
    for supplier in Supplier.objects.order_by("name"):
        products_supplied = supplier.products_supplied or []
        for supplied_name in products_supplied:
            if normalize_action_message(supplied_name) == normalized:
                return supplier
    return None


def maybe_auto_generate_replenishment(action, data):
    if not CONVERSATION_MEMORY.get("auto_replenishment_enabled"):
        return None
    if not isinstance(data, dict):
        return None
    if action not in {"get_product_stock", "update_product", "delete_purchase_order", "create_waste", "update_waste"}:
        return None

    product_name = data.get("name") or data.get("product_name")
    stock = data.get("stock", data.get("remaining_stock"))
    minimum_stock = data.get("minimum_stock")
    configured_threshold = CONVERSATION_MEMORY.get("auto_replenishment_threshold")
    effective_threshold = configured_threshold if configured_threshold is not None else minimum_stock
    if not product_name or effective_threshold is None or stock is None or stock >= effective_threshold or effective_threshold <= 0:
        return None

    supplier = find_supplier_for_product(product_name)
    if not supplier:
        return {
            "reply_note": f" No he podido generar el pedido automaticamente porque no hay un proveedor asociado a {product_name}.",
            "auto_order": None,
        }

    quantity = max(int(effective_threshold) - int(stock), 1)
    order = create_purchase_order(
        {
            "supplier_id": str(supplier.id),
            "items": [{"product_name": product_name, "quantity": quantity}],
        }
    )
    record_action_audit(
        "create_purchase_order",
        f"Pedido automatico generado para reponer {product_name}.",
        order,
    )
    remember_supplier_name(supplier.name)
    return {
        "reply_note": (
            f" Se ha generado automaticamente un pedido a {supplier.name} por {quantity} unidad(es) de {product_name}."
        ),
        "auto_order": order,
    }


def audit_entities_for(action, data):
    if not isinstance(data, dict):
        return "", "", "", []

    entity_type = ""
    entity_name = ""
    entity_id = ""
    related_entities = []

    def add_related(item_type, name="", item_id=""):
        related_entities.append({"type": item_type, "name": name or "", "id": item_id or ""})

    if action in {"create_product", "update_product", "get_product_stock", "query_products"}:
        entity_type = "product"
        entity_name = data.get("name", "")
        entity_id = data.get("id", "")
    elif action == "add_product_stock":
        entity_type = "product"
        entity_name = data.get("name", "")
        entity_id = data.get("id", "")
    elif action == "delete_product":
        entity_type = "product"
        entity_name = data.get("name", "")
        entity_id = data.get("id", "")
    elif action == "create_supplier" or action == "update_supplier" or action == "delete_supplier":
        entity_type = "supplier"
        entity_name = data.get("name", "")
        entity_id = data.get("id", "")
    elif action in {
        "create_purchase_order",
        "receive_purchase_order",
        "cancel_purchase_order",
        "update_purchase_order",
        "delete_purchase_order",
        "query_purchase_orders",
        "complete_purchase_order",
        "cancel_latest_purchase_order",
    }:
        entity_type = "purchase_order"
        entity_name = data.get("id", "")
        entity_id = data.get("id", "")
        if data.get("supplier_name"):
            add_related("supplier", data.get("supplier_name"), data.get("supplier_id", ""))
        for item in data.get("items", []):
            add_related("product", item.get("product_name", ""), item.get("product_id", ""))
        for item in data.get("affected_products", []):
            add_related("product", item.get("product_name", ""), item.get("product_id", ""))
    elif action in {"create_waste", "update_waste", "delete_waste"}:
        entity_type = "waste"
        entity_name = data.get("product_name", "") or data.get("id", "")
        entity_id = data.get("id", "")
        if data.get("product_name"):
            add_related("product", data.get("product_name"), data.get("product_id", ""))

    return entity_type, entity_name, entity_id, related_entities


def record_action_audit(action, reply, data):
    entity_type, entity_name, entity_id, related_entities = audit_entities_for(action, data or {})
    payload = data if isinstance(data, dict) else {}
    if isinstance(data, list):
        payload = {"results_count": len(data)}
    record_audit(
        action=action,
        summary=reply,
        entity_type=entity_type,
        entity_name=entity_name,
        entity_id=entity_id,
        related_entities=related_entities,
        payload=payload,
    )


def audit_history_reply(target_label, requested_limit, total_available):
    if total_available == 0:
        return f"No hay trazas registradas para {target_label}."
    if total_available < requested_limit:
        return (
            f"No puedo mostrar {requested_limit} registros porque solo existen {total_available}. "
            f"Te enseno los {total_available} disponibles."
        )
    return f"Te muestro los ultimos {requested_limit} registros de trazabilidad para {target_label}."


def execute_audit_history_request(data):
    limit = int(data.get("limit") or 10)
    if data.get("audit_scope") == "supplier":
        supplier_name = data["supplier_name"]
        entries, total = supplier_audit_history(supplier_name, limit)
        return (
            audit_history_reply(f"el proveedor {supplier_name}", limit, total),
            [serialize_audit_entry(entry) for entry in entries],
        )

    entries, total = deleted_products_history(limit)
    return (
        audit_history_reply("los productos eliminados", limit, total),
        [serialize_audit_entry(entry) for entry in entries],
    )


def _functional_error_code(exc):
    if isinstance(exc, DoesNotExist):
        return "not_found"
    if isinstance(exc, NotUniqueError):
        return "not_unique"
    if isinstance(exc, PurchaseOrderDomainError):
        return exc.__class__.__name__
    if isinstance(exc, ValidationError):
        return "validation_error"
    return "functional_error"


def build_pending_product_selection(intent, data):
    if not isinstance(data, dict):
        return None

    if intent == "add_product_stock" and data.get("name") and data.get("quantity") is not None:
        return {
            "intent": intent,
            "reply": f"Completo la entrada de inventario para {data['name']}.",
            "name": data["name"],
            "quantity": int(data["quantity"]),
        }

    if intent == "create_purchase_order":
        items = data.get("items") or []
        if data.get("supplier_name") and items:
            item = items[0]
            if item.get("product_name") and item.get("quantity") is not None:
                pending = {
                    "intent": intent,
                    "reply": f"Completo el pedido pendiente para {data['supplier_name']}.",
                    "supplier_name": data["supplier_name"],
                    "items": items,
                }
                return pending

    return None


def maybe_store_pending_action(intent, result_data, exc):
    message = str(exc)
    if "He encontrado varios productos" not in message:
        clear_pending_action()
        return

    pending_action = build_pending_product_selection(intent, result_data)
    if pending_action:
        remember_pending_action(pending_action)
    else:
        clear_pending_action()


def maybe_store_duplicate_update_action(intent, result_data):
    if not isinstance(result_data, dict):
        clear_pending_action()
        return

    if intent == "create_product" and result_data.get("name"):
        remember_pending_action(
            {
                "intent": "duplicate_create_product",
                "name": result_data["name"],
                "update_data": result_data,
            }
        )
        return

    if intent == "create_supplier" and result_data.get("name"):
        remember_pending_action(
            {
                "intent": "duplicate_create_supplier",
                "name": result_data["name"],
                "update_data": result_data,
            }
        )
        return

    clear_pending_action()


def parse_pending_duplicate_update_command(message, context):
    normalized_message = normalize_action_message(message).strip()
    if normalized_message not in {"actualiza", "actualizar", "actualizalo", "actualizala", "si actualiza"}:
        return None

    pending = (context or {}).get("pending_action")
    if not isinstance(pending, dict):
        return None

    update_data = dict(pending.get("update_data") or {})
    if not update_data.get("name"):
        return None

    if pending.get("intent") == "duplicate_create_product":
        return {
            "intent": "update_product",
            "reply": f"Actualizo el producto {update_data['name']}.",
            "data": update_data,
        }

    if pending.get("intent") == "duplicate_create_supplier":
        return {
            "intent": "update_supplier",
            "reply": f"Actualizo el proveedor {update_data['name']}.",
            "data": update_data,
        }

    return None


def parse_auto_replenishment_command(message):
    normalized_message = normalize_action_message(message).strip()
    if not any(
        term in normalized_message
        for term in [
            "reposicion",
            "reabastecimiento",
            "pedido automatico",
            "pedidos automaticos",
            "alertas automaticas de stock",
            "automatizaciones",
            "sin stock",
        ]
    ):
        return None

    if any(term in normalized_message for term in ["desactiva", "desactivar", "deshabilita", "deshabilitar", "apaga"]):
        return {
            "intent": "configure_auto_replenishment",
            "reply": "Desactivo la reposicion automatica de pedidos.",
            "data": {"enabled": False, "threshold": None},
        }

    if "sin stock" in normalized_message:
        return {
            "intent": "configure_auto_replenishment",
            "reply": "Activo la reposicion automatica para productos sin stock.",
            "data": {"enabled": True, "threshold": 1},
        }

    threshold_match = None
    if "menos de" in normalized_message:
        import re

        threshold_match = re.search(r"menos de (?P<threshold>\d+)", normalized_message)
    threshold = int(threshold_match.group("threshold")) if threshold_match else None

    if any(term in normalized_message for term in ["activa", "activar", "habilita", "habilitar", "enciende"]):
        return {
            "intent": "configure_auto_replenishment",
            "reply": "Activo la reposicion automatica de pedidos por stock bajo.",
            "data": {"enabled": True, "threshold": threshold},
        }

    return None


def parse_demo_shortcut_command(message, context):
    import re

    normalized_message = normalize_action_message(message).strip()
    normalized_message = normalized_message.strip("¿?!. ")
    context = context or {}
    last_supplier_name = context.get("last_supplier_name")
    last_purchase_order_id = context.get("last_purchase_order_id")

    if normalized_message in {
        "cual es el email del ultimo proveedor registrado?",
        "cual es el email del ultimo proveedor registrado",
    }:
        if not last_supplier_name:
            return {
                "intent": "missing_data",
                "reply": "No tengo un proveedor reciente en memoria. Registra o consulta antes un proveedor.",
                "data": {},
            }
        return {
            "intent": "list_suppliers",
            "reply": f"Consulto los datos del proveedor {last_supplier_name}.",
            "data": {"name": last_supplier_name},
        }

    previous_phone_match = re.search(
        r"actualiza el telefono del proveedor anterior a (?P<phone>[\d+ ]+)$",
        normalized_message,
    )
    if previous_phone_match:
        if not last_supplier_name:
            return {
                "intent": "missing_data",
                "reply": "No tengo un proveedor anterior en memoria. Indica el nombre del proveedor.",
                "data": {},
            }
        return {
            "intent": "update_supplier",
            "reply": f"Actualizo el teléfono del proveedor {last_supplier_name}.",
            "data": {"name": last_supplier_name, "phone": previous_phone_match.group("phone").strip()},
        }

    if normalized_message in {
        "cuantos productos hay registrados actualmente?",
        "cuantos productos hay registrados actualmente",
    }:
        return {
            "intent": "query_products",
            "reply": "Calculo cuántos productos hay registrados actualmente.",
            "data": {"kind": "products_count"},
        }

    add_same_order_match = re.search(
        r"(?:anade|añade) tambien (?P<quantity>\d+) (?P<product>.+?) al mismo pedido$",
        normalized_message,
    )
    if add_same_order_match:
        if not last_purchase_order_id:
            return {
                "intent": "missing_data",
                "reply": "No tengo un pedido reciente en memoria. Crea primero el pedido al que quieres añadir líneas.",
                "data": {},
            }
        product_name = add_same_order_match.group("product").strip()
        return {
            "intent": "update_purchase_order",
            "reply": "Añado una nueva línea al último pedido creado.",
            "data": {
                "id": last_purchase_order_id,
                "append_items": True,
                "items": [{"product_name": product_name.title(), "quantity": int(add_same_order_match.group("quantity"))}],
            },
        }

    waste_match = re.search(
        r"registra un desecho de (?P<quantity>\d+) unidades de (?P<product>.+?) por (?P<reason>deterioro|obsolescencia)$",
        normalized_message,
    )
    if waste_match:
        return {
            "intent": "create_waste",
            "reply": f"Registro el desecho de {waste_match.group('product').title()}.",
            "data": {
                "product_name": waste_match.group("product").title(),
                "quantity": int(waste_match.group("quantity")),
                "reason": waste_match.group("reason"),
            },
        }

    if normalized_message == "genera una grafica de productos con menos stock":
        return {
            "intent": "query_products",
            "reply": "Genero una gráfica con los productos de menor stock.",
            "data": {"kind": "low_stock_chart", "threshold": 5},
        }

    if normalized_message in {
        "muestrame los productos con menos de 5 unidades",
        "muestrame los productos con menos de 5 unidades.",
    }:
        return {
            "intent": "query_products",
            "reply": "Consulto los productos con menos de 5 unidades.",
            "data": {"kind": "low_stock", "threshold": 5},
        }

    expensive_match = re.search(r"dame los (?P<limit>\d+) productos mas caros$", normalized_message)
    if expensive_match:
        return {
            "intent": "query_products",
            "reply": "Consulto los productos más caros.",
            "data": {"kind": "top_expensive", "limit": int(expensive_match.group("limit"))},
        }

    if normalized_message in {
        "calcula el valor economico total del almacen",
        "calcula el valor economico total del almacen.",
    }:
        return {
            "intent": "query_products",
            "reply": "Calculo el valor económico total del almacén.",
            "data": {"kind": "inventory_value"},
        }

    return None


def execute_agent_action(message, provider_name=None, request_id=None):
    process_expired_products()
    provider = get_provider(provider_name)
    with ObservedOperation("agent_chat", request_id=request_id, provider=provider.name) as operation:
        intent = "fallback"
        try:
            conversation_context = get_conversation_context()
            confirmed_action = parse_confirmation_token(message.strip())
            if confirmed_action:
                result = confirmed_action
            else:
                direct_auto_replenishment = parse_auto_replenishment_command(message)
                if direct_auto_replenishment:
                    result = direct_auto_replenishment
                else:
                    demo_shortcut = parse_demo_shortcut_command(message, conversation_context)
                    if demo_shortcut:
                        result = demo_shortcut
                    else:
                        direct_pending_update = parse_pending_duplicate_update_command(message, conversation_context)
                        if direct_pending_update:
                            result = direct_pending_update
                        else:
                            result = provider.generate_response(message, context=conversation_context)
            intent = result.get("intent", "fallback")
            provider_status = result.get("provider_status")

            increment_metric("agent_intent_total", tags={"provider": provider.name, "intent": intent})

            if result.get("llm_error"):
                operation.failure("technical", "llm_unavailable", intent=intent)
                return build_agent_response(
                    provider.name,
                    "fallback",
                    "El LLM no pudo procesar la solicitud, contacte con el administrador.",
                    None,
                    success=False,
                    provider_status=provider_status,
                    error_type="technical",
                    request_id=operation.request_id,
                )

            confirmation_response = maybe_require_confirmation(message, result)
            if confirmation_response:
                operation.success(intent="confirmation_required", confirmed=False)
                confirmation_response["request_id"] = operation.request_id
                return confirmation_response

            if intent == "help":
                clear_pending_action()
                response = build_agent_response(
                    provider.name, intent, result["reply"], None, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent in ["confirmation_required", "missing_data"]:
                response = build_agent_response(
                    provider.name,
                    intent,
                    result["reply"],
                    result.get("data"),
                    success=False,
                    provider_status=provider_status,
                    error_type="functional",
                    request_id=operation.request_id,
                )
                operation.failure("functional", intent, intent=intent)
                return response

            if intent == "configure_auto_replenishment":
                clear_pending_action()
                enabled = bool(result["data"].get("enabled"))
                threshold = result["data"].get("threshold")
                set_auto_replenishment(enabled, threshold)
                response = build_agent_response(
                    provider.name,
                    intent,
                    "La reposicion automatica ha quedado configurada.",
                    {"enabled": enabled, "threshold": threshold},
                    provider_status=provider_status,
                    request_id=operation.request_id,
                )
                operation.success(intent=intent)
                return response

            if intent == "show_audit_history":
                clear_pending_action()
                reply, rows = execute_audit_history_request(result["data"])
                response = build_agent_response(
                    provider.name, intent, reply, rows, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "list_products":
                clear_pending_action()
                data = list_products()
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "query_products":
                clear_pending_action()
                query_data = result.get("data", {})
                data = product_insights(
                    query_data.get("kind"),
                    limit=query_data.get("limit"),
                    threshold=query_data.get("threshold"),
                    search=query_data.get("search"),
                )
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "get_product_stock":
                product = get_product_document_by_name(result["data"]["name"])
                clear_pending_action()
                remember_product_name(product.name)
                data = {
                    "name": product.name,
                    "stock": product.stock,
                    "minimum_stock": product.minimum_stock,
                    "unit_price": float(product.unit_price),
                }
                reply = f"Tienes {product.stock} unidad(es) de {product.name} en el inventario."
                response = build_agent_response(
                    provider.name, intent, reply, data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "create_product":
                clear_pending_action()
                data = create_product(result["data"])
                remember_product_name(data.get("name"))
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "add_product_stock":
                try:
                    product = get_product_document_by_name(result["data"]["name"])
                    data = update_product(str(product.id), {"stock": product.stock + int(result["data"]["quantity"])})
                except DoesNotExist:
                    data = create_product(
                        {
                            "name": result["data"]["name"],
                            "stock": int(result["data"]["quantity"]),
                            "unit_price": 0,
                            "description": "",
                            "category": "Inventario",
                            "minimum_stock": 0,
                        }
                    )
                clear_pending_action()
                remember_product_name(data.get("name"))
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "update_product":
                product = get_product_document_by_name(result["data"]["name"])
                payload = {key: value for key, value in result["data"].items() if key != "name"}
                if "new_name" in payload:
                    payload["name"] = payload.pop("new_name")
                data = update_product(str(product.id), payload)
                clear_pending_action()
                remember_product_name(data.get("name"))
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "delete_product":
                product = get_product_document_by_name(result["data"]["name"])
                clear_pending_action()
                remember_product_name(product.name)
                quantity = result["data"].get("quantity")
                data = delete_product(str(product.id), quantity=quantity)
                data["name"] = product.name
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "delete_all_products":
                clear_pending_action()
                data = clear_products_inventory()
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "list_suppliers":
                clear_pending_action()
                if result.get("data", {}).get("name"):
                    supplier = get_supplier_document_by_name(result["data"]["name"])
                    data = serialize_supplier(supplier)
                    remember_supplier_name(supplier.name)
                else:
                    data = list_suppliers()
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "create_supplier":
                clear_pending_action()
                data = create_supplier(result["data"])
                remember_supplier_name(data.get("name"))
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "update_supplier":
                supplier = get_supplier_document_by_name(result["data"]["name"])
                payload = {key: value for key, value in result["data"].items() if key != "name"}
                if "new_name" in payload:
                    payload["name"] = payload.pop("new_name")
                data = update_supplier(str(supplier.id), payload)
                clear_pending_action()
                remember_supplier_name(data.get("name"))
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "delete_supplier":
                supplier = get_supplier_document_by_name(result["data"]["name"])
                clear_pending_action()
                remember_supplier_name(supplier.name)
                data = delete_supplier(str(supplier.id))
                data["name"] = supplier.name
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "delete_all_suppliers":
                clear_pending_action()
                data = clear_suppliers()
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "list_purchase_orders":
                clear_pending_action()
                data = list_purchase_orders(status=result.get("data", {}).get("status"))
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "query_purchase_orders":
                clear_pending_action()
                data = order_insights(result.get("data", {}).get("kind"))
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "create_purchase_order":
                supplier = get_supplier_document_by_name(result["data"]["supplier_name"])
                remember_supplier_name(supplier.name)
                payload = {
                    "supplier_id": str(supplier.id),
                    "items": result["data"]["items"],
                }
                data = create_purchase_order(payload)
                remember_purchase_order_id(data.get("id"))
                clear_pending_action()
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "receive_purchase_order":
                if result["data"].get("id"):
                    data = receive_purchase_order(result["data"]["id"], received_items=result["data"].get("items"))
                else:
                    supplier = get_supplier_document_by_name(result["data"]["supplier_name"])
                    remember_supplier_name(supplier.name)
                    data = receive_latest_purchase_order_for_supplier(
                        str(supplier.id), received_items=result["data"].get("items")
                    )
                clear_pending_action()
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "cancel_purchase_order":
                if result["data"].get("id"):
                    data = cancel_purchase_order(result["data"]["id"], reason=result["data"].get("reason", ""))
                else:
                    supplier = get_supplier_document_by_name(result["data"]["supplier_name"])
                    remember_supplier_name(supplier.name)
                    open_order = list_purchase_orders(status="pending")
                    matching_order = next(
                        (order for order in open_order if order["supplier_id"] == str(supplier.id)),
                        None,
                    )
                    if not matching_order:
                        raise ValidationError(f"No hay pedidos abiertos para el proveedor {supplier.name}.")
                    data = cancel_purchase_order(matching_order["id"], reason=result["data"].get("reason", ""))
                clear_pending_action()
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "update_purchase_order":
                if result["data"].get("append_items"):
                    data = append_items_to_purchase_order(result["data"]["id"], result["data"]["items"])
                    remember_supplier_name(data.get("supplier_name"))
                else:
                    supplier = get_supplier_document_by_name(result["data"]["supplier_name"])
                    remember_supplier_name(supplier.name)
                    payload = {
                        "supplier_id": str(supplier.id),
                        "items": result["data"]["items"],
                        "status": result["data"].get("status", "received"),
                    }
                    data = update_purchase_order(result["data"]["id"], payload)
                remember_purchase_order_id(data.get("id"))
                clear_pending_action()
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "delete_purchase_order":
                clear_pending_action()
                data = delete_purchase_order(result["data"]["id"])
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "complete_purchase_order":
                clear_pending_action()
                data = mark_purchase_order_completed(result["data"]["id"])
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "cancel_latest_purchase_order":
                clear_pending_action()
                data = cancel_latest_purchase_order()
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "list_waste":
                clear_pending_action()
                data = list_waste_records()
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "create_waste":
                clear_pending_action()
                data = create_waste_record(result["data"])
                remember_product_name(data.get("product_name"))
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "update_waste":
                clear_pending_action()
                data = update_waste_record(result["data"]["id"], result["data"])
                remember_product_name(data.get("product_name"))
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "delete_waste":
                clear_pending_action()
                data = delete_waste_record(result["data"]["id"])
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "delete_all_waste":
                clear_pending_action()
                data = clear_waste_records()
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            if intent == "show_statistics":
                clear_pending_action()
                data = statistics_overview()
                response = build_agent_response(
                    provider.name, intent, result["reply"], data, provider_status=provider_status, request_id=operation.request_id
                )
                operation.success(intent=intent)
                return response

            response = build_agent_response(
                provider.name, intent, result["reply"], None, provider_status=provider_status, request_id=operation.request_id
            )
            operation.success(intent=intent)
            return response

        except DoesNotExist as exc:
            message = str(exc).strip() or "No se ha encontrado el registro solicitado. Revisa el nombre o consulta la lista antes de operar."
            operation.failure("functional", _functional_error_code(exc), intent=intent)
            return build_agent_response(
                provider.name,
                intent,
                message,
                None,
                success=False,
                error_type="functional",
                request_id=operation.request_id,
            )
        except NotUniqueError as exc:
            maybe_store_duplicate_update_action(intent, result.get("data"))
            operation.failure("functional", _functional_error_code(exc), intent=intent)
            return build_agent_response(
                provider.name,
                intent,
                "Ya existe un registro con esos datos. Usa otro nombre o responde 'actualiza' para aplicar estos datos al registro existente.",
                None,
                success=False,
                error_type="functional",
                request_id=operation.request_id,
            )
        except (ValidationError, PurchaseOrderDomainError) as exc:
            maybe_store_pending_action(intent, result.get("data"), exc)
            operation.failure("functional", _functional_error_code(exc), intent=intent)
            reply = readable_validation_error(exc) if isinstance(exc, ValidationError) else str(exc)
            return build_agent_response(
                provider.name,
                intent,
                reply,
                None,
                success=False,
                error_type="functional",
                request_id=operation.request_id,
            )
        except Exception:
            operation.failure("technical", "unexpected_exception", intent=intent)
            return build_agent_response(
                provider.name,
                intent,
                "No se pudo completar la operacion. Contacte con el administrador.",
                None,
                success=False,
                error_type="technical",
                request_id=operation.request_id,
            )


def build_agent_response(provider, action, reply, data, success=True, provider_status=None, error_type=None, request_id=None):
    if success and action != "fallback":
        reply = professional_reply(action, reply, data)
        auto_replenishment = maybe_auto_generate_replenishment(action, data)
        if auto_replenishment:
            reply = f"{reply}{auto_replenishment['reply_note']}"
            if auto_replenishment.get("auto_order") and isinstance(data, dict):
                data = {**data, "auto_generated_order": auto_replenishment["auto_order"]}
        data = sanitize_agent_data(data)
        if action != "show_audit_history":
            record_action_audit(action, reply, data)

    return {
        "success": success,
        "provider": provider,
        "action": action,
        "reply": reply,
        "data": data,
        "provider_status": provider_status,
        "error_type": error_type,
        "request_id": request_id,
    }


def professional_reply(action, fallback_reply, data):
    if action in ["help", "confirmation_required", "missing_data", "show_audit_history"]:
        return fallback_reply

    if action == "configure_auto_replenishment":
        return (
            "La reposicion automatica de pedidos por stock bajo esta activada."
            if data.get("enabled")
            else "La reposicion automatica de pedidos por stock bajo esta desactivada."
        )

    if action == "get_product_stock":
        note = proactive_note_for(action, data)
        return f"{fallback_reply}{note}" if note else fallback_reply

    if action.startswith("list_"):
        if isinstance(data, dict):
            return "Consulta realizada correctamente. Se muestran los datos solicitados."
        total = len(data) if isinstance(data, list) else 0
        return f"Consulta realizada correctamente. Se han encontrado {total} registro(s)."

    if action in ["query_products", "query_purchase_orders"]:
        if isinstance(data, list):
            return f"Consulta realizada correctamente. Se han encontrado {len(data)} resultado(s)."
        if isinstance(data, dict) and data.get("products_count") is not None and data.get("_query_kind") == "products_count":
            return f"Actualmente hay {data['products_count']} producto(s) registrados."
        if isinstance(data, dict) and data.get("chart_type"):
            return "Grafica preparada correctamente. Se muestra en el panel el analisis solicitado."
        return "Consulta calculada correctamente. Se muestran los datos solicitados en el panel."

    if action == "add_product_stock":
        reply = "Inventario actualizado correctamente. Las unidades quedan reflejadas en el panel en vivo."
        note = proactive_note_for(action, data)
        return f"{reply}{note}" if note else reply

    if action == "create_supplier":
        sync_status = data.get("_sync_status") if isinstance(data, dict) else None
        supplier_name = data.get("name", "indicado") if isinstance(data, dict) else "indicado"
        if sync_status == "already_exists":
            return f"El proveedor {supplier_name} ya existia y no ha sido necesario aplicar cambios."
        if sync_status == "updated_existing":
            return f"El proveedor {supplier_name} ya existia. Sus datos se han actualizado correctamente en el ERP."

    if action.startswith("create_"):
        reply = "Registro creado correctamente. La informacion queda disponible para nuevas consultas desde el chat."
        note = proactive_note_for(action, data)
        return f"{reply}{note}" if note else reply

    if action == "update_supplier" and isinstance(data, dict) and data.get("_sync_status") == "unchanged":
        return "El proveedor ya tenia esos datos. No ha sido necesario aplicar cambios."

    if action.startswith("update_"):
        reply = "Registro actualizado correctamente. Los cambios se han aplicado en el ERP."
        note = proactive_note_for(action, data)
        return f"{reply}{note}" if note else reply

    if action == "receive_purchase_order":
        if data.get("status") == "partially_received":
            return "Recepción parcial registrada correctamente. El pedido sigue abierto con unidades pendientes."
        return "Pedido recibido correctamente. Las unidades del pedido ya se han incorporado al inventario."

    if action == "cancel_purchase_order":
        if data.get("status") == "closed_partial":
            return "Pedido cerrado parcialmente. Se cancela lo pendiente y se conserva lo ya recibido."
        return "Pedido cancelado correctamente. Ya no quedan unidades pendientes por recibir."

    if action == "complete_purchase_order":
        return "Pedido actualizado correctamente. El cambio de estado queda reflejado en el ERP."

    if action == "cancel_latest_purchase_order":
        return "Ultimo pedido cancelado correctamente. El stock asociado se ha ajustado."

    if action.startswith("delete_"):
        if action == "delete_product" and isinstance(data, dict) and data.get("removed_quantity"):
            reply = (
                f"Stock ajustado correctamente. Se han descontado {data['removed_quantity']} unidad(es) "
                f"de {data.get('name')} y quedan {data.get('stock')}."
            )
            note = proactive_note_for(action, data)
            return f"{reply}{note}" if note else reply
        reply = "Registro eliminado correctamente. La operacion ha quedado aplicada en el ERP."
        note = proactive_note_for(action, data)
        return f"{reply}{note}" if note else reply

    if action == "show_statistics":
        return "Analisis generado correctamente. Se muestran los indicadores disponibles con los datos actuales."

    return fallback_reply


def readable_validation_error(exc):
    message = str(exc)
    replacements = {
        "ValidationError": "Validacion",
        "Integer value is too small": "El valor indicado es inferior al minimo permitido",
        "Float value is too small": "El valor indicado es inferior al minimo permitido",
        "Decimal value is too small": "El importe indicado es inferior al minimo permitido",
    }
    for original, replacement in replacements.items():
        message = message.replace(original, replacement)
    return message


def sanitize_agent_data(data):
    if isinstance(data, dict):
        return {key: value for key, value in data.items() if not key.startswith("_")}
    return data
