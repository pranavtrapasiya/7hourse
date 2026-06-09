"""
View package — re-exports all view callables for URL routing.
"""
from .dashboard import dashboard
from .settings_views import settings_view, migrate_product_codes
from .products import (
    product_add, product_edit, product_delete, product_restore,
    product_permanent_delete, deleted_products, product_list,
    product_detail, export_products_csv,
)
from .inventory import location_view, delete_inventory_entry
from .orders import (
    order_create, order_list, order_detail_api, order_save_api,
    order_edit, order_delete,
)
from .ajax import (
    ajax_subcategories, ajax_product_search, ajax_preview_code,
    ajax_order_locations, api_product_search,
)
from .auth import register_view, logout_view
from .wishlist import wishlist_list, wishlist_toggle
from .approvals import (
    approval_requests, approve_user_api, reject_user_api,
    bulk_approve_api, bulk_reject_api, approval_history_api,
)
from .admin_control import (
    admin_control_center, admin_users, admin_user_detail,
    admin_audit_logs, admin_user_activity_api,
)

__all__ = [
    'dashboard',
    'settings_view', 'migrate_product_codes',
    'product_add', 'product_edit', 'product_delete', 'product_restore',
    'product_permanent_delete', 'deleted_products', 'product_list',
    'product_detail', 'export_products_csv',
    'location_view', 'delete_inventory_entry',
    'order_create', 'order_list', 'order_detail_api', 'order_save_api',
    'order_edit', 'order_delete',
    'ajax_subcategories', 'ajax_product_search', 'ajax_preview_code',
    'ajax_order_locations', 'api_product_search',
    'register_view', 'logout_view',
    'wishlist_list', 'wishlist_toggle',
    'approval_requests', 'approve_user_api', 'reject_user_api',
    'bulk_approve_api', 'bulk_reject_api', 'approval_history_api',
    'admin_control_center', 'admin_users', 'admin_user_detail',
    'admin_audit_logs', 'admin_user_activity_api',
]
