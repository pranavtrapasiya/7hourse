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
            rejected_user_ids = set(
                ApprovalLog.objects.filter(action='rejected')
                .values_list('target_user_id', flat=True).distinct()
            ) - set(
                ApprovalLog.objects.filter(action='approved')
                .values_list('target_user_id', flat=True).distinct()
            )
            pending_count = User.objects.filter(
                is_active=False, is_superuser=False
            ).exclude(id__in=rejected_user_ids).count()

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