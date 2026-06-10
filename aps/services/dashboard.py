"""
Dashboard statistics for user and administrator views.
"""
from datetime import timedelta

from django.db.models import Count, Sum, Q
from django.utils import timezone

from aps.models import (
    AuditLog, Category, Order, Product, SubCategory,
    User, WarehouseInventory, WishlistItem,
)
from aps.permissions import (
    filter_orders_own, filter_products_own,
    filter_inventory_own, is_administrator,
)


class DashboardService:

    @staticmethod
    def company_stats(user):
        """Metrics for administrators."""
        now = timezone.now()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        orders = filter_orders_own(user)
        return {
            'total_products': filter_products_own(user).filter(is_deleted=False).count(),
            'total_categories': Category.objects.filter(created_by=user).count(),
            'total_subcategories': SubCategory.objects.filter(category__created_by=user).count(),
            'total_inventory': filter_inventory_own(user).count(),
            'total_orders': orders.count(),
            'total_users': User.objects.filter(is_superuser=False).count(),
            'active_users': User.objects.filter(is_active=True, is_superuser=False).count(),
            'pending_users': User.objects.filter(is_active=False, is_superuser=False).count(),
            'orders_this_week': orders.filter(created_at__gte=week_ago).count(),
            'orders_this_month': orders.filter(created_at__gte=month_ago).count(),
            'total_order_value': orders.aggregate(total=Sum('total_amount'))['total'] or 0,
            'recent_products': filter_products_own(user).filter(is_deleted=False).select_related(
                'category', 'subcategory'
            )[:10],
            'recent_activity': AuditLog.objects.filter(user=user).select_related('user')[:15],
        }

    @staticmethod
    def user_stats(user):
        """Personal statistics for a regular staff member."""
        now = timezone.now()
        week_ago = now - timedelta(days=7)
        orders_qs = filter_orders_own(user)
        products_qs = filter_products_own(user)
        inventory_qs = filter_inventory_own(user)

        pending_payment = orders_qs.filter(remaining_to_pay__gt=0).count()
        recent_orders = orders_qs.select_related('product').order_by('-created_at')[:10]
        recent_activity = AuditLog.objects.filter(user=user).order_by('-created_at')[:10]

        return {
            'total_products': products_qs.filter(is_deleted=False).count(),
            'total_categories': Category.objects.filter(created_by=user).count(),
            'total_subcategories': SubCategory.objects.filter(category__created_by=user).count(),
            'total_inventory': inventory_qs.count(),
            'my_orders': orders_qs.count(),
            'my_orders_this_week': orders_qs.filter(created_at__gte=week_ago).count(),
            'my_order_value': orders_qs.aggregate(total=Sum('total_amount'))['total'] or 0,
            'pending_payment_orders': pending_payment,
            'wishlist_count': WishlistItem.objects.filter(user=user).count(),
            'recent_products': products_qs.filter(is_deleted=False).select_related(
                'category', 'subcategory'
            )[:10],
            'recent_orders': recent_orders,
            'recent_activity': recent_activity,
            'is_admin': is_administrator(user),
        }
