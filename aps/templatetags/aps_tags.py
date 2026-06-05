from django import template
from django.urls import resolve, Resolver404

register = template.Library()


@register.simple_tag
def active_class(request, url_name):
    """Return 'active' if the current URL matches the given named URL."""
    try:
        match = resolve(request.path)
        if match.url_name == url_name:
            return "active"
    except Resolver404:
        pass
    return ""


@register.filter(name="currency")
def currency_filter(value):
    """Format a number as Indian Rupee currency."""
    try:
        amount = float(value)
        if amount == int(amount):
            return f"₹{int(amount):,}"
        return f"₹{amount:,.2f}"
    except (ValueError, TypeError):
        return f"₹{value}"
