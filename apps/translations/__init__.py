### Here be dragons.
# Django decided to require that ForeignKeys be unique.  That's generally
# reasonable, but Translations break that in their quest for all things unholy.
# Here we monkeypatch the error collector Django uses in validation to skip any
# messages generated by Translations. (Django #13284)
import re

from django.conf import settings
from django.core.management import validation
from django.utils.translation import trans_real

from jinja2.filters import do_dictsort

Parent = validation.ModelErrorCollection


class ModelErrorCollection(Parent):
    skip = ("Field 'id' under model '\w*Translation' must "
            "have a unique=True constraint.")

    def add(self, context, error):
        if not re.match(self.skip, error):
            Parent.add(self, context, error)

validation.ModelErrorCollection = ModelErrorCollection


LOCALES = [(trans_real.to_locale(k).replace('_', '-'), v) for k, v in
           do_dictsort(settings.LANGUAGES)]
