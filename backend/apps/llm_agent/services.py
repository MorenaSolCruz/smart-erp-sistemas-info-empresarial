from mongoengine.errors import DoesNotExist, NotUniqueError, ValidationError

from apps.llm_agent.providers import get_provider
from apps.products.models import Product
from apps.products.services import create_product, delete_product, list_products, update_product
from apps.purchase_orders.services import create_purchase_order
from apps.statistics.services import statistics_overview
from apps.suppliers.services import create_supplier, get_supplier_document_by_name, list_suppliers
from apps.waste.services import create_waste_record


def execute_agent_action(message, provider_name=None):
    provider = get_provider(provider_name)
    result = provider.generate_response(message, context={})
    intent = result.get("intent", "fallback")

    try:
        if intent == "list_products":
            data = list_products()
            return build_agent_response(provider.name, intent, result["reply"], data)

        if intent == "create_product":
            data = create_product(result["data"])
            return build_agent_response(provider.name, intent, result["reply"], data)

        if intent == "update_product":
            product = Product.objects.get(name__iexact=result["data"]["name"])
            payload = {key: value for key, value in result["data"].items() if key != "name"}
            data = update_product(str(product.id), payload)
            return build_agent_response(provider.name, intent, result["reply"], data)

        if intent == "delete_product":
            product = Product.objects.get(name__iexact=result["data"]["name"])
            data = delete_product(str(product.id))
            return build_agent_response(provider.name, intent, result["reply"], data)

        if intent == "list_suppliers":
            data = list_suppliers()
            return build_agent_response(provider.name, intent, result["reply"], data)

        if intent == "create_supplier":
            data = create_supplier(result["data"])
            return build_agent_response(provider.name, intent, result["reply"], data)

        if intent == "create_purchase_order":
            supplier = get_supplier_document_by_name(result["data"]["supplier_name"])
            payload = {
                "supplier_id": str(supplier.id),
                "items": result["data"]["items"],
            }
            data = create_purchase_order(payload)
            return build_agent_response(provider.name, intent, result["reply"], data)

        if intent == "create_waste":
            data = create_waste_record(result["data"])
            return build_agent_response(provider.name, intent, result["reply"], data)

        if intent == "show_statistics":
            data = statistics_overview()
            return build_agent_response(provider.name, intent, result["reply"], data)

        return build_agent_response(provider.name, intent, result["reply"], None)

    except DoesNotExist:
        return build_agent_response(provider.name, intent, "No se ha encontrado la entidad solicitada.", None, success=False)
    except NotUniqueError:
        return build_agent_response(provider.name, intent, "Ya existe un registro con esos datos.", None, success=False)
    except ValidationError as exc:
        return build_agent_response(provider.name, intent, str(exc), None, success=False)
    except Exception as exc:
        return build_agent_response(provider.name, intent, f"Ha ocurrido un error: {exc}", None, success=False)


def build_agent_response(provider, action, reply, data, success=True):
    return {
        "success": success,
        "provider": provider,
        "action": action,
        "reply": reply,
        "data": data,
    }
