from django.contrib import admin
from .models import (
    Category, SubCategory, Product,
    WarehouseInventory, CartonImage, InventoryProductImage, InventoryVideo,
    ProductCodeSettings, ProductCodeSequence,
    Order,
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
    list_display = ['product_name', 'asin_code', 'sh_code', 'category', 'subcategory', 'created_at']
    list_filter = ['category', 'subcategory']
    search_fields = ['product_name', 'asin_code', 'sh_code']
    readonly_fields = ['asin_code', 'created_at']


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
    list_display = ['product', 'location_number', 'price', 'carton_piece', 'cbm', 'created_at']
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