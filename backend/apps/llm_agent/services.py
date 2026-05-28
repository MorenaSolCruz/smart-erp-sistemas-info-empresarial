from mongoengine.errors import DoesNotExist, NotUniqueError, ValidationError

from apps.audit.services import (
    deleted_products_history,
    record_audit,
    serialize_audit_entry,
    supplier_audit_history,
)
from apps.llm_agent.providers import confirmation_token, get_provider
from apps.products.services import (
    clear_products_inventory,
    create_product,
    delete_product,
    get_product_document_by_name,
    list_products,
    product_insights,
    update_product,
)
from apps.purchase_orders.services import (
    cancel_latest_purchase_order,
    mark_purchase_order_completed,
    create_purchase_order,
    delete_purchase_order,
    list_purchase_orders,
    order_insights,
    update_purchase_order,
)
from apps.statistics.services import statistics_overview
from apps.suppliers.services import (
    clear_suppliers,
    create_supplier,
    delete_supplier,
    get_supplier_document_by_name,
    list_suppliers,
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


CONVERSATION_MEMORY = {
    "last_supplier_name": None,
    "last_product_name": None,
    "auto_replenishment_enabled": False,
    "auto_replenishment_threshold": None,
}


def get_conversation_context():
    return {
        "last_supplier_name": CONVERSATION_MEMORY.get("last_supplier_name"),
        "last_product_name": CONVERSATION_MEMORY.get("last_product_name"),
        "auto_replenishment_enabled": CONVERSATION_MEMORY.get("auto_replenishment_enabled", False),
        "auto_replenishment_threshold": CONVERSATION_MEMORY.get("auto_replenishment_threshold"),
    }


def remember_supplier_name(supplier_name):
    if supplier_name:
        CONVERSATION_MEMORY["last_supplier_name"] = supplier_name


def remember_product_name(product_name):
    if product_name:
        CONVERSATION_MEMORY["last_product_name"] = product_name


def set_auto_replenishment(enabled, threshold=None):
    CONVERSATION_MEMORY["auto_replenishment_enabled"] = bool(enabled)
    if threshold is not None:
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
    if intent == "delete_all_products":
        return "Esta accion eliminara todo el inventario de productos. Quieres eliminarlo? Responde si o no."
    if intent == "delete_all_suppliers":
        return "Esta accion eliminara todos los proveedores sin pedidos asociados. Quieres continuar? Responde si o no."
    if intent == "delete_all_waste":
        return "Esta accion eliminara todos los desechos registrados. Quieres continuar? Responde si o no."
    return "La accion solicitada requiere confirmacion. Quieres continuar? Responde si o no."


def maybe_require_confirmation(message, result):
    intent = result.get("intent")
    sensitive_intents = {"delete_all_products", "delete_all_suppliers", "delete_all_waste"}
    if intent not in sensitive_intents:
        return None
    if result.get("confirmed"):
        return None

    normalized_message = normalize_action_message(message).strip()
    if intent in sensitive_intents and normalized_message.startswith("confirma "):
        return None

    return {
        "success": False,
        "provider": "assistant",
        "action": "confirmation_required",
        "reply": confirmation_prompt_for(intent, result.get("data", {})),
        "data": {
            "pending_action": intent,
            "confirmation_token": confirmation_token(intent, result.get("reply"), result.get("data", {})),
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
    if not product_name or minimum_stock is None or stock is None or stock >= minimum_stock or minimum_stock <= 0:
        return None

    supplier = find_supplier_for_product(product_name)
    if not supplier:
        return {
            "reply_note": f" No he podido generar el pedido automaticamente porque no hay un proveedor asociado a {product_name}.",
            "auto_order": None,
        }

    quantity = max(int(minimum_stock) - int(stock), 1)
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
    elif action in {"create_purchase_order", "update_purchase_order", "delete_purchase_order", "complete_purchase_order", "cancel_latest_purchase_order"}:
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


def execute_agent_action(message, provider_name=None):
    process_expired_products()
    provider = get_provider(provider_name)
    result = provider.generate_response(message, context=get_conversation_context())
    intent = result.get("intent", "fallback")
    provider_status = result.get("provider_status")

    confirmation_response = maybe_require_confirmation(message, result)
    if confirmation_response:
        return confirmation_response

    try:
        if intent == "help":
            return build_agent_response(provider.name, intent, result["reply"], None, provider_status=provider_status)

        if intent in ["confirmation_required", "missing_data"]:
            return build_agent_response(provider.name, intent, result["reply"], result.get("data"), success=False, provider_status=provider_status)

        if intent == "configure_auto_replenishment":
            enabled = bool(result["data"].get("enabled"))
            threshold = result["data"].get("threshold")
            set_auto_replenishment(enabled, threshold)
            return build_agent_response(
                provider.name,
                intent,
                "La reposicion automatica ha quedado configurada.",
                {"enabled": enabled, "threshold": threshold},
                provider_status=provider_status,
            )

        if intent == "show_audit_history":
            reply, rows = execute_audit_history_request(result["data"])
            return build_agent_response(provider.name, intent, reply, rows, provider_status=provider_status)

        if intent == "list_products":
            data = list_products()
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "query_products":
            query_data = result.get("data", {})
            data = product_insights(
                query_data.get("kind"),
                limit=query_data.get("limit"),
                threshold=query_data.get("threshold"),
                search=query_data.get("search"),
            )
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "get_product_stock":
            product = get_product_document_by_name(result["data"]["name"])
            remember_product_name(product.name)
            data = {
                "name": product.name,
                "stock": product.stock,
                "minimum_stock": product.minimum_stock,
                "unit_price": float(product.unit_price),
            }
            reply = f"Tienes {product.stock} unidad(es) de {product.name} en el inventario."
            return build_agent_response(provider.name, intent, reply, data, provider_status=provider_status)

        if intent == "create_product":
            data = create_product(result["data"])
            remember_product_name(data.get("name"))
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

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
            remember_product_name(data.get("name"))
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "update_product":
            product = get_product_document_by_name(result["data"]["name"])
            payload = {key: value for key, value in result["data"].items() if key != "name"}
            if "new_name" in payload:
                payload["name"] = payload.pop("new_name")
            data = update_product(str(product.id), payload)
            remember_product_name(data.get("name"))
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "delete_product":
            product = get_product_document_by_name(result["data"]["name"])
            remember_product_name(product.name)
            data = delete_product(str(product.id))
            data["name"] = product.name
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "delete_all_products":
            data = clear_products_inventory()
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "list_suppliers":
            data = list_suppliers()
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "create_supplier":
            data = create_supplier(result["data"])
            remember_supplier_name(data.get("name"))
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "update_supplier":
            supplier = get_supplier_document_by_name(result["data"]["name"])
            payload = {key: value for key, value in result["data"].items() if key != "name"}
            if "new_name" in payload:
                payload["name"] = payload.pop("new_name")
            data = update_supplier(str(supplier.id), payload)
            remember_supplier_name(data.get("name"))
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "delete_supplier":
            supplier = get_supplier_document_by_name(result["data"]["name"])
            remember_supplier_name(supplier.name)
            data = delete_supplier(str(supplier.id))
            data["name"] = supplier.name
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "delete_all_suppliers":
            data = clear_suppliers()
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "list_purchase_orders":
            data = list_purchase_orders()
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "query_purchase_orders":
            data = order_insights(result.get("data", {}).get("kind"))
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "create_purchase_order":
            supplier = get_supplier_document_by_name(result["data"]["supplier_name"])
            remember_supplier_name(supplier.name)
            payload = {
                "supplier_id": str(supplier.id),
                "items": result["data"]["items"],
            }
            data = create_purchase_order(payload)
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "update_purchase_order":
            supplier = get_supplier_document_by_name(result["data"]["supplier_name"])
            remember_supplier_name(supplier.name)
            payload = {
                "supplier_id": str(supplier.id),
                "items": result["data"]["items"],
                "status": result["data"].get("status", "received"),
            }
            data = update_purchase_order(result["data"]["id"], payload)
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "delete_purchase_order":
            data = delete_purchase_order(result["data"]["id"])
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "complete_purchase_order":
            data = mark_purchase_order_completed(result["data"]["id"])
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "cancel_latest_purchase_order":
            data = cancel_latest_purchase_order()
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "list_waste":
            data = list_waste_records()
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "create_waste":
            data = create_waste_record(result["data"])
            remember_product_name(data.get("product_name"))
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "update_waste":
            data = update_waste_record(result["data"]["id"], result["data"])
            remember_product_name(data.get("product_name"))
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "delete_waste":
            data = delete_waste_record(result["data"]["id"])
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "delete_all_waste":
            data = clear_waste_records()
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "show_statistics":
            data = statistics_overview()
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        return build_agent_response(provider.name, intent, result["reply"], None, provider_status=provider_status)

    except DoesNotExist:
        return build_agent_response(
            provider.name,
            intent,
            "No se ha encontrado el registro solicitado. Revisa el nombre o consulta la lista antes de operar.",
            None,
            success=False,
        )
    except NotUniqueError:
        return build_agent_response(
            provider.name,
            intent,
            "Ya existe un registro con esos datos. Usa otro nombre o actualiza el registro existente.",
            None,
            success=False,
        )
    except ValidationError as exc:
        return build_agent_response(provider.name, intent, readable_validation_error(exc), None, success=False)
    except Exception as exc:
        return build_agent_response(
            provider.name,
            intent,
            f"No se pudo completar la operacion. Detalle: {exc}",
            None,
            success=False,
        )


def build_agent_response(provider, action, reply, data, success=True, provider_status=None):
    if success and action != "fallback":
        reply = professional_reply(action, reply, data)
        auto_replenishment = maybe_auto_generate_replenishment(action, data)
        if auto_replenishment:
            reply = f"{reply}{auto_replenishment['reply_note']}"
            if auto_replenishment.get("auto_order") and isinstance(data, dict):
                data = {**data, "auto_generated_order": auto_replenishment["auto_order"]}
        if action != "show_audit_history":
            record_action_audit(action, reply, data)

    return {
        "success": success,
        "provider": provider,
        "action": action,
        "reply": reply,
        "data": data,
        "provider_status": provider_status,
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
        total = len(data) if isinstance(data, list) else 0
        return f"Consulta realizada correctamente. Se han encontrado {total} registro(s)."

    if action in ["query_products", "query_purchase_orders"]:
        if isinstance(data, list):
            return f"Consulta realizada correctamente. Se han encontrado {len(data)} resultado(s)."
        return "Consulta calculada correctamente. Se muestran los datos solicitados en el panel."

    if action == "add_product_stock":
        reply = "Inventario actualizado correctamente. Las unidades quedan reflejadas en el panel en vivo."
        note = proactive_note_for(action, data)
        return f"{reply}{note}" if note else reply

    if action.startswith("create_"):
        reply = "Registro creado correctamente. La informacion queda disponible para nuevas consultas desde el chat."
        note = proactive_note_for(action, data)
        return f"{reply}{note}" if note else reply

    if action.startswith("update_"):
        reply = "Registro actualizado correctamente. Los cambios se han aplicado en el ERP."
        note = proactive_note_for(action, data)
        return f"{reply}{note}" if note else reply

    if action in ["complete_purchase_order"]:
        return "Pedido actualizado correctamente. El cambio de estado queda reflejado en el ERP."

    if action == "cancel_latest_purchase_order":
        return "Ultimo pedido cancelado correctamente. El stock asociado se ha ajustado."

    if action.startswith("delete_"):
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
