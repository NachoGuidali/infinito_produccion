from django import template
from django.utils.html import strip_tags

register = template.Library()


@register.filter
def meta_desc(texto, largo=155):
    """
    Deja un texto listo para un meta description: sin HTML, sin saltos de
    linea y recortado. Las descripciones de los cursos vienen con saltos que
    ensucian el atributo.
    """
    if not texto:
        return ""
    limpio = " ".join(strip_tags(str(texto)).split())
    if len(limpio) <= largo:
        return limpio
    return limpio[:largo].rsplit(" ", 1)[0] + "..."
