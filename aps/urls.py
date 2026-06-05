from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('settings/', views.settings_view, name='settings'),
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.product_add, name='product_add'),
    path('products/<int:pk>/', views.product_detail, name='product_detail'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('products/<int:pk>/restore/', views.product_restore, name='product_restore'),
    path('products/<int:pk>/permanent-delete/', views.product_permanent_delete, name='product_permanent_delete'),
    path('products/deleted/', views.deleted_products, name='deleted_products'),
    path('products/export/', views.export_products_csv, name='export_products_csv'),
    path('location/', views.location_view, name='location'),
    path('location/entry/<int:pk>/delete/', views.delete_inventory_entry, name='delete_inventory_entry'),
    # ── Order Module ──
    path('orders/', views.order_list, name='order_list'),
    path('orders/new/', views.order_create, name='order_create'),
    path('orders/save/', views.order_save_api, name='order_save_api'),
    path('orders/<int:pk>/', views.order_detail_api, name='order_detail_api'),
    path('orders/<int:pk>/edit/', views.order_edit, name='order_edit'),
    path('orders/<int:pk>/delete/', views.order_delete, name='order_delete'),
    # AJAX endpoints
    path('ajax/subcategories/', views.ajax_subcategories, name='ajax_subcategories'),
    path('ajax/products/search/', views.ajax_product_search, name='ajax_product_search'),
    path('ajax/preview-code/', views.ajax_preview_code, name='ajax_preview_code'),
    path('ajax/order/locations/', views.ajax_order_locations, name='ajax_order_locations'),
    path('settings/migrate-codes/', views.migrate_product_codes, name='migrate_product_codes'),
    path('api/products/search/', views.api_product_search, name='api_product_search'),
]