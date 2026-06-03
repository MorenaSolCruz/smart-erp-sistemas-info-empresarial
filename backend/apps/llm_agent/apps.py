from django.apps import AppConfig


class LlmAgentConfig(AppConfig):
    # Registra el modulo del agente conversacional dentro de Django.
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.llm_agent"

