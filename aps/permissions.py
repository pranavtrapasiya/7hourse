"""
Role-based access control for the single-company WMS.

Administrators (is_staff or is_superuser) have unrestricted access.
Regular users access shared catalog/inventory data but only manage
their own orders and user-generated records unless explicitly granted.
"""
from functools import wraps

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect

from .models import Order, Product, WarehouseInventory, UserProfile


def is_administrator(user):
    """Company managers with full system access."""
    return user.is_authenticated and user.is_active and (
        user.is_staff or user.is_superuser
    )


def is_active_approved(user):
    """Approved company staff member."""
    return user.is_authenticated and user.is_active


def get_user_profile(user):
    """Return or create the user's permission profile."""
    if not user.is_authenticated:
        return None
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def can_export(user):
    if is_administrator(user):
        return True
    profile = get_user_profile(user)
    return profile and profile.can_export


def can_manage_settings(user):
    if is_administrator(user):
        return True
    profile = get_user_profile(user)
    return profile and profile.can_manage_settings


def can_delete_products(user):
    if is_administrator(user):
        return True
    profile = get_user_profile(user)
    return profile and profile.can_delete_products


def can_delete_inventory(user):
    if is_administrator(user):
        return True
    profile = get_user_profile(user)
    return profile and profile.can_delete_inventory


def can_manage_all_orders(user):
    if is_administrator(user):
        return True
    profile = get_user_profile(user)
    return profile and profile.can_manage_all_orders


def can_view_order(user, order):
    if is_administrator(user) or can_manage_all_orders(user):
        return True
    return order.created_by_id == user.id


def can_edit_order(user, order):
    return can_view_order(user, order)


def can_delete_order(user, order):
    return can_edit_order(user, order)


def filter_orders_for_user(user, queryset=None):
    """Scope order querysets to what the user may see."""
    if queryset is None:
        queryset = Order.objects.all()
    if is_administrator(user) or can_manage_all_orders(user):
        return queryset
    return queryset.filter(created_by=user)


def filter_orders_own(user, queryset=None):
    """Return only orders created by this user (regardless of admin status)."""
    if queryset is None:
        queryset = Order.objects.all()
    return queryset.filter(created_by=user)


def get_order_for_user(user, pk):
    """Fetch an order with ownership enforcement."""
    order = Order.objects.select_related('product', 'location', 'created_by').get(pk=pk)
    if not can_view_order(user, order):
        raise PermissionDenied('You do not have permission to access this order.')
    return order


# ── Product Ownership ─────────────────────────────────────────────────────────

def can_view_product(user, product):
    """Check if user can view a product."""
    if is_administrator(user):
        return True
    return product.created_by_id == user.id


def can_edit_product(user, product):
    """Check if user can edit a product."""
    if is_administrator(user):
        return True
    return product.created_by_id == user.id


def can_delete_product(user, product):
    """Check if user can delete a product."""
    return can_edit_product(user, product)


def filter_products_for_user(user, queryset=None):
    """Scope product querysets to what the user may see."""
    if queryset is None:
        queryset = Product.objects.all()
    if is_administrator(user):
        return queryset
    return queryset.filter(created_by=user)


def filter_products_own(user, queryset=None):
    """Return only products created by this user (regardless of admin status)."""
    if queryset is None:
        queryset = Product.objects.all()
    return queryset.filter(created_by=user)


def get_product_for_user(user, pk):
    """Fetch a product with ownership enforcement."""
    product = Product.objects.select_related('category', 'subcategory', 'created_by', 'updated_by').get(pk=pk)
    if not can_view_product(user, product):
        raise PermissionDenied('You do not have permission to access this product.')
    return product


# ── Inventory Ownership ───────────────────────────────────────────────────────

def can_view_inventory(user, inventory):
    """Check if user can view inventory."""
    if is_administrator(user):
        return True
    return inventory.created_by_id == user.id


def can_edit_inventory(user, inventory):
    """Check if user can edit inventory."""
    if is_administrator(user):
        return True
    return inventory.created_by_id == user.id


def can_delete_inventory_item(user, inventory):
    """Check if user can delete inventory."""
    return can_edit_inventory(user, inventory)


def filter_inventory_for_user(user, queryset=None):
    """Scope inventory querysets to what the user may see."""
    if queryset is None:
        queryset = WarehouseInventory.objects.all()
    if is_administrator(user):
        return queryset
    return queryset.filter(created_by=user)


def filter_inventory_own(user, queryset=None):
    """Return only inventory entries created by this user (regardless of admin status)."""
    if queryset is None:
        queryset = WarehouseInventory.objects.all()
    return queryset.filter(created_by=user)


def get_inventory_for_user(user, pk):
    """Fetch inventory with ownership enforcement."""
    inventory = WarehouseInventory.objects.select_related('product', 'created_by', 'updated_by').get(pk=pk)
    if not can_view_inventory(user, inventory):
        raise PermissionDenied('You do not have permission to access this inventory.')
    return inventory


def admin_required(view_func):
    """Require an active administrator."""
    check = user_passes_test(
        lambda u: is_administrator(u),
        login_url='/login/',
    )
    return login_required(check(view_func))


def permission_required(check_func, message='You do not have permission to perform this action.'):
    """Decorator factory for permission checks on views."""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if not is_active_approved(request.user):
                return redirect('login')
            if not check_func(request.user):
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': message}, status=403)
                raise PermissionDenied(message)
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def handle_permission_denied(request, exception=None):
    """Return appropriate response for permission errors."""
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse(
            {'success': False, 'error': str(exception) if exception else 'Permission denied.'},
            status=403,
        )
    from django.contrib import messages
    messages.error(request, str(exception) if exception else 'You do not have permission.')
    return redirect('dashboard')


def permission_denied_view(request, exception=None):
    """Django handler403 entry point."""
    return handle_permission_denied(request, exception)


# ── Security Decorators for IDOR Prevention ───────────────────────────────────

def ownership_required(model_class, pk_kwarg='pk', lookup_field='pk'):
    """
    Decorator to enforce ownership-based access control.
    Prevents IDOR vulnerabilities by checking object ownership.

    Args:
        model_class: The model class to check ownership for
        pk_kwarg: The URL parameter name containing the object ID (default: 'pk')
        lookup_field: The field to use for lookup (default: 'pk')
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if not is_active_approved(request.user):
                return redirect('login')

            # Allow administrators unrestricted access
            if is_administrator(request.user):
                return view_func(request, *args, **kwargs)

            # Get the object ID from URL parameters
            object_id = kwargs.get(pk_kwarg)
            if not object_id:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Object ID required.'}, status=400)
                raise PermissionDenied('Object ID required.')

            # Build the lookup filter
            lookup_kwargs = {lookup_field: object_id}

            try:
                obj = model_class.objects.get(**lookup_kwargs)
            except model_class.DoesNotExist:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Object not found.'}, status=404)
                raise PermissionDenied('Object not found.')

            # Check ownership by looking for created_by field
            if hasattr(obj, 'created_by'):
                if obj.created_by_id != request.user.id:
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        return JsonResponse({'success': False, 'error': 'You do not have permission to access this object.'}, status=403)
                    raise PermissionDenied('You do not have permission to access this object.')
            elif hasattr(obj, 'user'):
                # For models with a 'user' field instead of 'created_by'
                if obj.user_id != request.user.id:
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        return JsonResponse({'success': False, 'error': 'You do not have permission to access this object.'}, status=403)
                    raise PermissionDenied('You do not have permission to access this object.')
            else:
                # Model doesn't have ownership fields - allow access
                return view_func(request, *args, **kwargs)

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def admin_or_owner_required(model_class, pk_kwarg='pk', lookup_field='pk'):
    """
    Decorator that allows administrators or object owners.
    Similar to ownership_required but more explicit about the access pattern.

    Args:
        model_class: The model class to check ownership for
        pk_kwarg: The URL parameter name containing the object ID (default: 'pk')
        lookup_field: The field to use for lookup (default: 'pk')
    """
    return ownership_required(model_class, pk_kwarg, lookup_field)
