import datetime

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Case, When, Value, IntegerField
from django.http import JsonResponse

from aps.models import Product, SubCategory, WarehouseInventory
from aps.permissions import business_user_required, filter_inventory_own, filter_products_own


@business_user_required
def ajax_subcategories(request):
    category_id = request.GET.get('category_id')
    subcategories = []
    if category_id:
        subcategories = list(
            SubCategory.objects.filter(
                category_id=category_id, category__created_by=request.user
            ).values('id', 'name')
        )
    return JsonResponse({'subcategories': subcategories})


@business_user_required
def ajax_product_search(request):
    q = request.GET.get('q', '').strip()
    results = []
    if len(q) >= 1:
        qs = filter_products_own(request.user).filter(is_deleted=False).select_related(
            'category', 'subcategory'
        ).filter(product_name__icontains=q).annotate(
            search_priority=Case(
                When(product_name__istartswith=q, then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            )
        ).order_by('search_priority', 'product_name')[:20]

        for p in qs:
            results.append({
                'id': p.id,
                'product_name': p.product_name,
                'product_code': p.asin_code or '',
                'asin_code': p.asin_code or '',
                'sh_code': p.sh_code or '',
                'category': p.category.name if p.category else '',
                'has_image': bool(p.main_image),
                'image_url': p.main_image.url if p.main_image else '',
            })
    return JsonResponse({'results': results, 'query': q})


@business_user_required
def ajax_preview_code(request):
    now = datetime.datetime.now()
    preview = f"{now.year}{now.strftime('%b').upper()}{now.strftime('%d')}0001"
    return JsonResponse({'preview': preview})


@business_user_required
def ajax_order_locations(request):
    product_id = request.GET.get('product_id')
    if not product_id:
        return JsonResponse({'locations': []})

    entries = filter_inventory_own(request.user).filter(product_id=product_id).order_by('-created_at')
    locations = [{
        'id': e.pk,
        'location_number': e.location_number or '—',
        'price': str(e.price),
        'cbm': f"{e.cbm.normalize():f}" if e.cbm else '0',
        'carton_piece': e.carton_piece,
        'remark': e.remark or '',
        'created_at': e.created_at.strftime('%d %b %Y') if e.created_at else '',
    } for e in entries]
    return JsonResponse({'locations': locations})


@business_user_required
def api_product_search(request):
    q = request.GET.get('q', '').strip()
    page_num = request.GET.get('page', 1)

    if not q:
        return JsonResponse({'suggestions': [], 'results': [], 'total': 0})

    qs = filter_products_own(request.user).filter(is_deleted=False).select_related(
        'category', 'subcategory'
    ).filter(
        Q(product_name__icontains=q) |
        Q(asin_code__icontains=q) |
        Q(category__name__icontains=q) |
        Q(subcategory__name__icontains=q) |
        Q(description__icontains=q) |
        Q(tags__icontains=q)
    ).annotate(
        search_priority=Case(
            When(product_name__istartswith=q, then=Value(1)),
            When(product_name__icontains=q, then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        )
    ).order_by('search_priority', 'product_name').distinct()

    total_count = qs.count()
    wishlist_ids = set(request.user.wishlist_items.values_list('product_id', flat=True))

    suggestions = [{
        'id': p.id,
        'product_name': p.product_name,
        'product_code': p.asin_code or '',
        'asin_code': p.asin_code or '',
        'category': p.category.name if p.category else '',
        'subcategory': p.subcategory.name if p.subcategory else '',
        'image_url': p.main_image.url if p.main_image else '',
        'has_image': bool(p.main_image),
    } for p in qs[:10]]

    paginator = Paginator(qs, 24)
    try:
        page_obj = paginator.page(page_num)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    results = [{
        'id': p.id,
        'product_name': p.product_name,
        'product_code': p.asin_code or '',
        'asin_code': p.asin_code or '',
        'category': p.category.name if p.category else '',
        'subcategory': p.subcategory.name if p.subcategory else '',
        'image_url': p.main_image.url if p.main_image else '',
        'has_image': bool(p.main_image),
        'wished': p.id in wishlist_ids,
        'created_at_formatted': p.created_at.strftime('%d %b %Y') if p.created_at else '',
    } for p in page_obj]

    return JsonResponse({
        'suggestions': suggestions,
        'results': results,
        'total': total_count,
    })
