from .models import Category, Product, WarehouseInventory


def sidebar_context(request):
    if request.user.is_authenticated:
        return {
            'total_products': Product.objects.filter(is_deleted=False).count(),
            'total_categories': Category.objects.count(),
            'total_inventory': WarehouseInventory.objects.count(),
        }
    return {}