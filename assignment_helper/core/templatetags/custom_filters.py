# core/templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter
def split_string(value, delimiter):
    """Split a string by the given delimiter and return a list."""
    return [s.strip() for s in value.split(delimiter) if s.strip()]