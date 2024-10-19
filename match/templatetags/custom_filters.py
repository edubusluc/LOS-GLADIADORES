from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    value = dictionary.get(key, None)
    return value[0] if value else None