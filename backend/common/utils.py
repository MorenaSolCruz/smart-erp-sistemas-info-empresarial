from decimal import Decimal


def decimal_to_float(value):
    """Convierte Decimal a float para respuestas JSON.

    MongoEngine guarda importes como Decimal para mantener precision, pero el
    frontend necesita numeros simples para tablas, KPIs y graficas.
    """
    if isinstance(value, Decimal):
        return float(value)
    return value


def normalize_text(value):
    """Limpia texto recibido del usuario o del LLM antes de compararlo."""
    return (value or "").strip()

