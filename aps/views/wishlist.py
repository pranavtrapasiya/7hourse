from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

from aps.models import AuditLog, Product, WishlistItem
from aps.services.audit import AuditService


@login_required
def wishlist_list(request):
    wishlist_items = request.user.wishlist_items.select_related(
        'product__category', 'product__subcategory'
    ).filter(product__is_deleted=False)
    products = [item.product for item in wishlist_items]

    return render(request, 'aps/wishlist.html', {
        'page_title': 'My Wishlist',
        'active_menu': 'wishlist',
        'products': products,
    })


@login_required
def wishlist_toggle(request, product_id):
    product = get_object_or_404(Product, pk=product_id, is_deleted=False)
    wishlist_item = WishlistItem.objects.filter(user=request.user, product=product)

    if wishlist_item.exists():
        wishlist_item.delete()
        wished = False
        message = f'Removed {product.product_name} from wishlist.'
        AuditService.log(
            request.user, AuditLog.ACTION_WISHLIST_REMOVE,
            object_type='wishlist', object_id=product.pk,
            object_repr=product.product_name, request=request,
        )
    else:
        WishlistItem.objects.create(user=request.user, product=product)
        wished = True
        message = f'Added {product.product_name} to wishlist.'
        AuditService.log(
            request.user, AuditLog.ACTION_WISHLIST_ADD,
            object_type='wishlist', object_id=product.pk,
            object_repr=product.product_name, request=request,
        )

    if (request.headers.get('x-requested-with') == 'XMLHttpRequest'
            or request.GET.get('ajax') == 'true' or request.method == 'POST'):
        return JsonResponse({
            'success': True,
            'wished': wished,
            'message': message,
            'wishlist_count': request.user.wishlist_items.count(),
        })

    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('product_list')
