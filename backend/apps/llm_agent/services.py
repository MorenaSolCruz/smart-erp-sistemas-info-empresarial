from mongoengine.errors import DoesNotExist, NotUniqueError, ValidationError

from apps.llm_agent.providers import get_provider
from apps.products.services import create_product, delete_product, get_product_document_by_name, list_products, update_product
from apps.purchase_orders.services import (
    create_purchase_order,
    delete_purchase_order,
    list_purchase_orders,
    update_purchase_order,
)
from apps.statistics.services import statistics_overview
from apps.suppliers.services import (
    create_supplier,
    delete_supplier,
    get_supplier_document_by_name,
    list_suppliers,
    update_supplier,
)
from apps.waste.services import create_waste_record, delete_waste_record, list_waste_records, update_waste_record


def execute_agent_action(message, provider_name=None):
    provider = get_provider(provider_name)
    result = provider.generate_response(message, context={})
    intent = result.get("intent", "fallback")
    provider_status = result.get("provider_status")

    try:
        if intent == "help":
            return build_agent_response(provider.name, intent, result["reply"], None, provider_status=provider_status)

        if intent in ["confirmation_required", "missing_data"]:
            return build_agent_response(provider.name, intent, result["reply"], None, success=False, provider_status=provider_status)

        if intent == "list_products":
            data = list_products()
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "create_product":
            data = create_product(result["data"])
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "update_product":
            product = get_product_document_by_name(result["data"]["name"])
            payload = {key: value for key, value in result["data"].items() if key != "name"}
            if "new_name" in payload:
                payload["name"] = payload.pop("new_name")
            data = update_product(str(product.id), payload)
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "delete_product":
            product = get_product_document_by_name(result["data"]["name"])
            data = delete_product(str(product.id))
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "list_suppliers":
            data = list_suppliers()
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "create_supplier":
            data = create_supplier(result["data"])
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "update_supplier":
            supplier = get_supplier_document_by_name(result["data"]["name"])
            payload = {key: value for key, value in result["data"].items() if key != "name"}
            if "new_name" in payload:
                payload["name"] = payload.pop("new_name")
            data = update_supplier(str(supplier.id), payload)
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "delete_supplier":
            supplier = get_supplier_document_by_name(result["data"]["name"])
            data = delete_supplier(str(supplier.id))
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "list_purchase_orders":
            data = list_purchase_orders()
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "create_purchase_order":
            supplier = get_supplier_document_by_name(result["data"]["supplier_name"])
            payload = {
                "supplier_id": str(supplier.id),
                "items": result["data"]["items"],
            }
            data = create_purchase_order(payload)
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "update_purchase_order":
            supplier = get_supplier_document_by_name(result["data"]["supplier_name"])
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

        if intent == "list_waste":
            data = list_waste_records()
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "create_waste":
            data = create_waste_record(result["data"])
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "update_waste":
            data = update_waste_record(result["data"]["id"], result["data"])
            return build_agent_response(provider.name, intent, result["reply"], data, provider_status=provider_status)

        if intent == "delete_waste":
            data = delete_waste_record(result["data"]["id"])
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
            f"No se pudo completar la operación. Detalle: {exc}",
            None,
            success=False,
        )


def build_agent_response(provider, action, reply, data, success=True, provider_status=None):
    if success and action != "fallback":
        reply = professional_reply(action, reply, data)

    return {
        "success": success,
        "provider": provider,
        "action": action,
        "reply": reply,
        "data": data,
        "provider_status": provider_status,
    }


def professional_reply(action, fallback_reply, data):
    if action in ["help", "confirmation_required", "missing_data"]:
        return fallback_reply

    if action.startswith("list_"):
        total = len(data) if isinstance(data, list) else 0
        return f"Consulta realizada correctamente. Se han encontrado {total} registro(s)."

    if action.startswith("create_"):
        return "Registro creado correctamente. La información queda disponible para nuevas consultas desde el chat."

    if action.startswith("update_"):
        return "Registro actualizado correctamente. Los cambios se han aplicado en el ERP."

    if action.startswith("delete_"):
        return "Registro eliminado correctamente. La operación ha quedado aplicada en el ERP."

    if action == "show_statistics":
        return "Análisis generado correctamente. Se muestran los indicadores disponibles con los datos actuales."

    return fallback_reply


def readable_validation_error(exc):
    message = str(exc)
    replacements = {
        "ValidationError": "Validación",
        "Integer value is too small": "El valor indicado es inferior al mínimo permitido",
        "Float value is too small": "El valor indicado es inferior al mínimo permitido",
        "Decimal value is too small": "El importe indicado es inferior al mínimo permitido",
    }
    for original, replacement in replacements.items():
        message = message.replace(original, replacement)
    return message
