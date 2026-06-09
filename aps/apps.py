from django.apps import AppConfig


class ApsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'aps'

    def ready(self):
        import aps.signals  # noqa: F401
