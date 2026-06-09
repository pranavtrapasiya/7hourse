# pyrefly: ignore [missing-import]
from django.contrib import admin
from .models import (
    Category, SubCategory, Product,
    WarehouseInventory, CartonImage, InventoryProductImage, InventoryVideo,
    ProductCodeSettings, ProductCodeSequence,
    Order, PendingApprovalUser, WishlistItem,
)


class SubCategoryInline(admin.TabularInline):
    model = SubCategory
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']
    inlines = [SubCategoryInline]


@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category']
    list_filter = ['category']
    search_fields = ['name', 'category__name']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['product_name', 'asin_code', 'sh_code', 'category', 'created_by', 'created_at']
    list_filter = ['category', 'subcategory', 'is_deleted']
    search_fields = ['product_name', 'asin_code', 'sh_code']
    readonly_fields = ['asin_code', 'created_at', 'updated_at']


class CartonImageInline(admin.TabularInline):
    model = CartonImage
    extra = 0
    readonly_fields = ['uploaded_at']


class InventoryProductImageInline(admin.TabularInline):
    model = InventoryProductImage
    extra = 0
    readonly_fields = ['uploaded_at']


class InventoryVideoInline(admin.TabularInline):
    model = InventoryVideo
    extra = 0
    readonly_fields = ['uploaded_at']


@admin.register(WarehouseInventory)
class WarehouseInventoryAdmin(admin.ModelAdmin):
    list_display = ['product', 'location_number', 'price', 'created_by', 'created_at']
    list_filter = ['product__category']
    search_fields = ['product__product_name', 'product__asin_code', 'location_number']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [CartonImageInline, InventoryProductImageInline, InventoryVideoInline]


@admin.register(ProductCodeSettings)
class ProductCodeSettingsAdmin(admin.ModelAdmin):
    list_display = ['enabled', 'prefix_format', 'sequence_length', 'reset_monthly']


@admin.register(ProductCodeSequence)
class ProductCodeSequenceAdmin(admin.ModelAdmin):
    list_display = ['year', 'month', 'last_sequence']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'product', 'location_number', 'quantity', 'price',
        'total_amount', 'order_date', 'created_by', 'created_at',
    ]
    list_filter = ['order_date', 'created_by']
    search_fields = ['product__product_name', 'location_number', 'remark']
    readonly_fields = ['remaining_to_pay', 'total_cbm', 'total_pieces', 'total_amount', 'created_at', 'updated_at']


# ── Custom UserAdmin for Account Approval ─────────────────────────────────────

from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from django.contrib.auth.models import User
from .models import ApprovalLog, AuditLog, UserProfile

admin.site.unregister(User)

@admin.register(User)
class CustomUserAdmin(DefaultUserAdmin):
    # Standard Django user admin without bypass actions
    pass


@admin.register(ApprovalLog)
class ApprovalLogAdmin(admin.ModelAdmin):
    list_display = ('target_user', 'action', 'performed_by', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('target_user__username', 'performed_by__username', 'note')
    readonly_fields = ('target_user', 'action', 'performed_by', 'note', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # Allow deletion when checking cascading delete rules (obj is None)
        # to allow deleting users, but block deleting individual logs from the log change view/form.
        if obj is not None:
            return False
        return True

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'created_at')
    search_fields = ('user__username', 'product__product_name')
    list_filter = ('created_at',)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'can_export', 'can_manage_all_orders', 'can_manage_settings',
        'can_delete_products', 'can_delete_inventory',
    )
    search_fields = ('user__username', 'user__email')
    list_filter = (
        'can_export', 'can_manage_all_orders', 'can_manage_settings',
        'can_delete_products', 'can_delete_inventory',
    )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'user', 'object_type', 'object_repr', 'ip_address', 'created_at')
    list_filter = ('action', 'object_type', 'created_at')
    search_fields = ('user__username', 'object_repr', 'details')
    readonly_fields = (
        'user', 'action', 'object_type', 'object_id', 'object_repr',
        'details', 'ip_address', 'user_agent', 'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        if obj is not None:
            return False
        return True

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions