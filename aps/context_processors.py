from django.contrib.auth.models import User

from aps.models import ApprovalLog, Category, Product, WarehouseInventory
from aps.permissions import (
    can_delete_products, can_export, can_manage_settings,
    is_administrator,
)


def sidebar_context(request):
    if request.user.is_authenticated:
        pending_count = 0
        if is_administrator(request.user):
            # Exclude rejected users from pending count
            from django.db.models import OuterRef, Subquery, Value
            from django.db.models.functions import Coalesce
            latest_log = ApprovalLog.objects.filter(target_user=OuterRef('pk')).order_by('-created_at')
            pending_count = User.objects.filter(is_active=False, is_superuser=False).annotate(
                latest_action=Coalesce(Subquery(latest_log.values('action')[:1]), Value(''))
            ).exclude(latest_action='rejected').count()

        wishlist_product_ids = set(request.user.wishlist_items.values_list('product_id', flat=True))
        return {
            'total_products': Product.objects.filter(
                is_deleted=False, created_by=request.user
            ).count(),
            'total_categories': Category.objects.filter(
                created_by=request.user
            ).count(),
            'total_inventory': WarehouseInventory.objects.filter(
                created_by=request.user
            ).count(),
            'pending_approvals_count': pending_count,
            'wishlist_product_ids': wishlist_product_ids,
            'wishlist_count': len(wishlist_product_ids),
            'is_administrator': is_administrator(request.user),
            'can_export': can_export(request.user),
            'can_manage_settings': can_manage_settings(request.user),
            'can_delete_products': can_delete_products(request.user),
        }
    return {}