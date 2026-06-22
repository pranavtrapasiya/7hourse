from django import template
from django.urls import resolve, Resolver404

from aps.permissions import (
    can_delete_inventory, can_delete_products, can_export,
    can_manage_all_orders, can_manage_settings, is_administrator,
)

register = template.Library()


@register.simple_tag
def active_class(request, *url_names):
    """Return 'active' if the current URL matches any of the given named URLs."""
    try:
        match = resolve(request.path)
        if match.url_name in url_names:
            return "active"
    except Resolver404:
        pass
    return ""


@register.filter
def is_admin(user):
    return is_administrator(user)


@register.filter
def can_user_export(user):
    return can_export(user)


@register.filter
def can_user_settings(user):
    return can_manage_settings(user)


@register.filter
def can_user_delete_products(user):
    return can_delete_products(user)


@register.filter
def can_user_delete_inventory(user):
    return can_delete_inventory(user)


@register.filter
def can_user_manage_all_orders(user):
    return can_manage_all_orders(user)


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


@register.filter(name="clean_decimal")
def clean_decimal(value):
    """Remove trailing zeros from a Decimal, avoiding scientific notation."""
    try:
        if value is None or str(value).strip() == '':
            return ''
        from decimal import Decimal
        d = value if isinstance(value, Decimal) else Decimal(str(value))
        return f"{d.normalize():f}"
    except (ValueError, TypeError):
        return value
