from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST

from aps.forms import OrderForm
from aps.models import AuditLog, Order, Product, WarehouseInventory
from aps.permissions import (
    can_edit_order, can_delete_order, filter_orders_own, get_order_for_user,
)
from aps.services.audit import AuditService


@login_required
def order_create(request):
    return render(request, 'aps/order_create.html', {
        'page_title': 'New Order',
        'active_menu': 'order',
    })


@login_required
def order_list(request):
    qs = filter_orders_own(
        request.user,
        Order.objects.select_related('product', 'location', 'created_by'),
    )

    search_query = request.GET.get('q', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    sort = request.GET.get('sort', '-created_at')

    if search_query:
        qs = qs.filter(
            Q(product__product_name__icontains=search_query) |
            Q(location_number__icontains=search_query) |
            Q(remark__icontains=search_query)
        )
    if date_from:
        qs = qs.filter(order_date__gte=date_from)
    if date_to:
        qs = qs.filter(order_date__lte=date_to)

    sort_map = {
        '-created_at': '-created_at', 'created_at': 'created_at',
        '-order_date': '-order_date', 'order_date': 'order_date',
        '-total_amount': '-total_amount', 'total_amount': 'total_amount',
    }
    qs = qs.order_by(sort_map.get(sort, '-created_at'))
    page_obj = Paginator(qs, 25).get_page(request.GET.get('page'))

    return render(request, 'aps/order_list.html', {
        'page_title': 'Orders',
        'active_menu': 'order_list',
        'page_obj': page_obj,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
        'sort': sort,
        'total_orders': qs.count(),
    })


@login_required
def order_detail_api(request, pk):
    try:
        order = get_order_for_user(request.user, pk)
    except (Order.DoesNotExist, PermissionDenied):
        return JsonResponse({'success': False, 'error': 'Order not found or access denied.'}, status=403)

    return JsonResponse({
        'id': order.pk,
        'product_name': order.product.product_name,
        'product_image': order.product.main_image.url if order.product.main_image else '',
        'location_number': order.location_number or '—',
        'quantity': order.quantity,
        'price': str(order.price),
        'deposit': str(order.deposit),
        'cbm': str(order.cbm),
        'carton_piece': order.carton_piece,
        'remaining_to_pay': str(order.remaining_to_pay),
        'total_cbm': str(order.total_cbm),
        'total_pieces': order.total_pieces,
        'total_amount': str(order.total_amount),
        'remark': order.remark or '—',
        'order_date': order.order_date.strftime('%d %b %Y') if order.order_date else '—',
        'created_by': order.created_by.username if order.created_by else '—',
        'created_at': order.created_at.strftime('%d %b %Y, %I:%M %p') if order.created_at else '—',
        'can_edit': can_edit_order(request.user, order),
        'can_delete': can_delete_order(request.user, order),
    })


@login_required
def order_save_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

    product_id = request.POST.get('product_id')
    location_id = request.POST.get('location_id') or None
    product = get_object_or_404(Product, pk=product_id, is_deleted=False)
    location = None
    if location_id:
        location = get_object_or_404(WarehouseInventory, pk=location_id)

    form = OrderForm(request.POST)
    if form.is_valid():
        order = form.save(commit=False)
        order.product = product
        order.location = location
        order.created_by = request.user
        order.updated_by = request.user
        order.save()
        AuditService.log_order(
            request.user, AuditLog.ACTION_ORDER_CREATED, order, request=request,
        )
        return JsonResponse({
            'success': True,
            'order_id': order.pk,
            'message': f'Order #{order.pk} saved successfully.',
        })
    errors = {field: errs[0] for field, errs in form.errors.items()}
    return JsonResponse({'success': False, 'errors': errors}, status=400)


@login_required
def order_edit(request, pk):
    try:
        order = get_order_for_user(request.user, pk)
    except (Order.DoesNotExist, PermissionDenied):
        return JsonResponse({'success': False, 'error': 'Order not found or access denied.'}, status=403)

    if not can_edit_order(request.user, order):
        return JsonResponse({'success': False, 'error': 'You cannot edit this order.'}, status=403)

    if request.method == 'GET':
        return JsonResponse({
            'id': order.pk,
            'product_id': order.product_id,
            'product_name': order.product.product_name,
            'location_id': order.location_id or '',
            'quantity': order.quantity,
            'price': str(order.price),
            'deposit': str(order.deposit),
            'cbm': str(order.cbm),
            'carton_piece': order.carton_piece,
            'location_number': order.location_number,
            'remark': order.remark,
            'order_date': order.order_date.strftime('%Y-%m-%d') if order.order_date else '',
        })

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

    form = OrderForm(request.POST, instance=order)
    if form.is_valid():
        order = form.save(commit=False)
        order.updated_by = request.user
        order.save()
        AuditService.log_order(
            request.user, AuditLog.ACTION_ORDER_UPDATED, order, request=request,
        )
        return JsonResponse({
            'success': True,
            'order_id': order.pk,
            'message': f'Order #{order.pk} updated successfully.',
        })
    errors = {field: errs[0] for field, errs in form.errors.items()}
    return JsonResponse({'success': False, 'errors': errors}, status=400)


@login_required
@require_POST
def order_delete(request, pk):
    try:
        order = get_order_for_user(request.user, pk)
    except (Order.DoesNotExist, PermissionDenied):
        return JsonResponse({'success': False, 'error': 'Order not found or access denied.'}, status=403)

    if not can_delete_order(request.user, order):
        return JsonResponse({'success': False, 'error': 'You cannot delete this order.'}, status=403)

    order_id = order.pk
    AuditService.log_order(
        request.user, AuditLog.ACTION_ORDER_DELETED, order, request=request,
    )
    order.delete()
    return JsonResponse({'success': True, 'message': f'Order #{order_id} deleted.'})
