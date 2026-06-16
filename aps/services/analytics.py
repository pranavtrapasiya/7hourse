"""
Analytics for the Admin Control Center.
"""
from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from aps.models import AuditLog, Order, Product, User, WarehouseInventory


class AnalyticsService:

    @staticmethod
    def user_performance(limit=20):
        """Per-user order and activity performance."""
        users = User.objects.filter(is_active=True, is_superuser=False).annotate(
            order_count=Count('orders'),
            total_value=Sum('orders__total_amount'),
            product_count=Count('products_created', distinct=True),
            inventory_count=Count('inventory_created', distinct=True),
        ).order_by('-order_count')[:limit]

        return [
            {
                'user': u,
                'order_count': u.order_count or 0,
                'total_value': u.total_value or 0,
                'product_count': u.product_count or 0,
                'inventory_count': u.inventory_count or 0,
            }
            for u in users
        ]

    @staticmethod
    def order_analytics(days=30):
        """Order trends over the last N days."""
        since = timezone.now() - timedelta(days=days)
        daily = (
            Order.objects.filter(created_at__gte=since)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(count=Count('id'), value=Sum('total_amount'))
            .order_by('day')
        )
        totals = Order.objects.filter(created_at__gte=since).aggregate(
            count=Count('id'),
            value=Sum('total_amount'),
            avg_value=Sum('total_amount'),
        )
        return {
            'daily': list(daily),
            'total_orders': totals['count'] or 0,
            'total_value': totals['value'] or 0,
        }

    @staticmethod
    def inventory_analytics():
        """Inventory distribution and growth metrics."""
        by_location = (
            WarehouseInventory.objects
            .values('location_number')
            .annotate(count=Count('id'))
            .order_by('-count')[:15]
        )
        week_ago = timezone.now() - timedelta(days=7)
        return {
            'total_entries': WarehouseInventory.objects.count(),
            'unique_locations': WarehouseInventory.objects.values('location_number').distinct().count(),
            'entries_this_week': WarehouseInventory.objects.filter(created_at__gte=week_ago).count(),
            'by_location': list(by_location),
            'products_with_inventory': Product.objects.filter(
                is_deleted=False, inventory_entries__isnull=False
            ).distinct().count(),
        }

    @staticmethod
    def activity_feed(limit=50):
        """Recent company-wide audit activity."""
        return AuditLog.objects.select_related('user').order_by('-created_at')[:limit]

    @staticmethod
    def user_activity(user, limit=30):
        """Activity for a specific user."""
        return AuditLog.objects.filter(
            Q(user=user) | Q(object_type='user', object_id=user.pk)
        ).select_related('user').order_by('-created_at')[:limit]

    @staticmethod
    def user_login_history(user, limit=20):
        """Login history for a specific user."""
        return AuditLog.objects.filter(
            user=user, action=AuditLog.ACTION_LOGIN
        ).order_by('-created_at')[:limit]

    @staticmethod
    def user_export_history(user, limit=20):
        """Export history for a specific user."""
        return AuditLog.objects.filter(
            user=user, action=AuditLog.ACTION_EXPORT
        ).order_by('-created_at')[:limit]

    @staticmethod
    def user_approval_history(user):
        """Approval history for a specific user."""
        from aps.models import ApprovalLog
        return ApprovalLog.objects.filter(
            target_user=user
        ).select_related('performed_by').order_by('-created_at')

    @staticmethod
    def user_comprehensive_stats(user):
        """Comprehensive statistics for a specific user."""
        from django.db.models import Count, Sum
        from aps.models import Product, WarehouseInventory, Order

        return {
            'total_products': Product.objects.filter(created_by=user, is_deleted=False).count(),
            'total_inventory': WarehouseInventory.objects.filter(created_by=user).count(),
            'total_orders': Order.objects.filter(created_by=user).count(),
            'total_order_value': Order.objects.filter(created_by=user).aggregate(
                total=Sum('total_amount')
            )['total'] or 0,
            'registration_date': user.date_joined,
            'approved_at': getattr(getattr(user, 'profile', None), 'approved_at', None),
            'last_activity': AuditLog.objects.filter(user=user).order_by('-created_at').first(),
            'account_status': 'Active' if user.is_active else 'Inactive',
        }
