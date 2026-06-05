from django.apps import AppConfig


class ApsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'aps'
    verbose_name = 'Inventory & Warehouse'

    def ready(self):
        """
        Monkey-patch Django 4.2's BaseContext.__copy__ to fix a Python 3.14
        incompatibility where super().__copy__() no longer returns an instance
        with a usable __dict__.

        Affected: django/template/context.py BaseContext.__copy__
        Root cause: Python 3.14 changed super() proxy copy semantics.
        """
        from copy import copy as _copy
        from django.template.context import BaseContext

        def _patched_context_copy(self):
            # Bypass super().__copy__() — create a blank instance and copy
            # the dict manually, then deep-copy the dicts stack.
            duplicate = self.__class__.__new__(self.__class__)
            duplicate.__dict__ = self.__dict__.copy()
            duplicate.dicts = _copy(self.dicts)
            return duplicate

        BaseContext.__copy__ = _patched_context_copy