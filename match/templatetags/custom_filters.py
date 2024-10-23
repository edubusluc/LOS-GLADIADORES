from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    if isinstance(dictionary, dict):
        value = dictionary.get(key, None)
        if isinstance(value, list):  # Maneja el caso de QueryDict
            return value[0] if value else None
        return value
    return None