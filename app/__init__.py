# Python 3.14 Compatibility Patch for Django Template Context Copying
try:
    import django.template.context
    def _context_copy(self):
        dup = self.__class__.__new__(self.__class__)
        dup.__dict__.update(self.__dict__)
        dup.dicts = self.dicts[:]
        return dup
    django.template.context.BaseContext.__copy__ = _context_copy
except Exception:
    pass
