import csv

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from aps.forms import ProductForm
from aps.models import AuditLog, Category, Product, SubCategory
from aps.permissions import (
    can_delete_products, can_export, permission_required,
    filter_products_own, get_product_for_user,
)
from aps.services.audit import AuditService


@login_required
def product_add(request):
    form = ProductForm(user=request.user)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            product = form.save(commit=False)
            product.created_by = request.user
            product.updated_by = request.user
            product.save()
            AuditService.log_product(
                request.user, AuditLog.ACTION_PRODUCT_CREATED, product, request=request,
            )
            messages.success(
                request,
                f'Product "{product.product_name}" added. ASIN: {product.asin_code}',
            )
            return redirect('product_detail', pk=product.pk)
        messages.error(request, 'Fix the form errors below.')

    return render(request, 'aps/product_add.html', {
        'page_title': 'Add Product',
        'active_menu': 'add_product',
        'product_form': form,
    })


@login_required
def product_edit(request, pk):
    product = get_product_for_user(request.user, pk)
    if product.is_deleted:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied('This product has been deleted.')
    form = ProductForm(instance=product, user=request.user)

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product, user=request.user)
        if form.is_valid():
            product = form.save(commit=False)
            product.updated_by = request.user
            product.save()
            AuditService.log_product(
                request.user, AuditLog.ACTION_PRODUCT_UPDATED, product, request=request,
            )
            messages.success(request, f'Product "{product.product_name}" updated.')
            return redirect('product_detail', pk=product.pk)
        messages.error(request, 'Fix the form errors.')

    return render(request, 'aps/product_add.html', {
        'page_title': 'Edit Product',
        'active_menu': 'product_list',
        'product': product,
        'product_form': form,
        'is_edit': True,
    })


@permission_required(can_delete_products, 'Only administrators can delete products.')
def product_delete(request, pk):
    product = get_product_for_user(request.user, pk)
    if product.is_deleted:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied('This product is already deleted.')
    if request.method == 'POST':
        name = product.product_name
        product.soft_delete()
        AuditService.log_product(
            request.user, AuditLog.ACTION_PRODUCT_DELETED, product,
            details={'name': name}, request=request,
        )
        messages.success(request, f'Product "{name}" moved to trash.')
        return redirect('product_list')
    return redirect('product_detail', pk=pk)


@permission_required(can_delete_products, 'Only administrators can restore products.')
def product_restore(request, pk):
    product = get_product_for_user(request.user, pk)
    if not product.is_deleted:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied('This product is not deleted.')
    if request.method == 'POST':
        product.restore()
        AuditService.log_product(
            request.user, AuditLog.ACTION_PRODUCT_RESTORED, product, request=request,
        )
        messages.success(request, f'Product "{product.product_name}" restored.')
        return redirect('product_detail', pk=pk)
    return redirect('deleted_products')


@permission_required(can_delete_products, 'Only administrators can permanently delete products.')
def product_permanent_delete(request, pk):
    product = get_product_for_user(request.user, pk)
    if not product.is_deleted:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied('This product is not deleted.')
    if request.method == 'POST':
        name = product.product_name
        product_id = product.pk
        if product.main_image:
            product.main_image.delete(save=False)
        AuditService.log(
            request.user, AuditLog.ACTION_PRODUCT_PERMANENT_DELETE,
            object_type='product', object_id=product_id,
            object_repr=name, request=request,
        )
        product.delete()
        messages.success(request, f'Product "{name}" permanently deleted.')
        return redirect('deleted_products')
    return redirect('deleted_products')


@permission_required(can_delete_products, 'Only administrators can view deleted products.')
def deleted_products(request):
    qs = filter_products_own(request.user).filter(is_deleted=True).select_related(
        'category', 'subcategory', 'created_by'
    ).order_by('-deleted_at')
    page_obj = Paginator(qs, 25).get_page(request.GET.get('page'))
    return render(request, 'aps/deleted_products.html', {
        'page_title': 'Deleted Products',
        'active_menu': 'product_list',
        'page_obj': page_obj,
    })


@login_required
def product_list(request):
    qs = filter_products_own(request.user).filter(is_deleted=False).select_related(
        'category', 'subcategory', 'created_by'
    )
    search_query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    subcategory_id = request.GET.get('subcategory', '')
    sort = request.GET.get('sort', '-created_at')

    if search_query:
        qs = qs.filter(product_name__icontains=search_query)
    if category_id:
        qs = qs.filter(category_id=category_id)
    if subcategory_id:
        qs = qs.filter(subcategory_id=subcategory_id)

    sort_map = {
        '-created_at': '-created_at', 'created_at': 'created_at',
        'product_name': 'product_name', '-product_name': '-product_name',
    }
    qs = qs.order_by(sort_map.get(sort, '-created_at'))
    page_obj = Paginator(qs, 25).get_page(request.GET.get('page'))

    return render(request, 'aps/product_list.html', {
        'page_title': 'Products',
        'active_menu': 'product_list',
        'page_obj': page_obj,
        'search_query': search_query,
        'category_id': category_id,
        'subcategory_id': subcategory_id,
        'sort': sort,
        'categories': Category.objects.filter(created_by=request.user),
        'subcategories': (
            SubCategory.objects.filter(category_id=category_id, category__created_by=request.user)
            if category_id else SubCategory.objects.filter(category__created_by=request.user)
        ),
    })


@login_required
def product_detail(request, pk):
    product = get_product_for_user(request.user, pk)
    inventory_entries = product.inventory_entries.select_related(
        'created_by', 'updated_by'
    ).prefetch_related('carton_images', 'product_images', 'video').order_by('-created_at')

    return render(request, 'aps/product_detail.html', {
        'page_title': product.product_name,
        'active_menu': 'product_list',
        'product': product,
        'inventory_entries': inventory_entries,
        'latest_inventory': inventory_entries.first(),
    })


@permission_required(can_export, 'Only administrators can export company data.')
def export_products_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="products_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    )
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow([
        'ID', 'Product Name', 'ASIN Code', 'SH Code',
        'Category', 'Subcategory', 'Description', 'Tags',
        'Created By', 'Created At',
    ])

    products = filter_products_own(request.user).filter(is_deleted=False).select_related(
        'category', 'subcategory', 'created_by'
    ).order_by('created_at').iterator(chunk_size=500)

    count = 0
    for p in products:
        writer.writerow([
            p.id, p.product_name, p.asin_code or '', p.sh_code or '',
            p.category.name if p.category else '',
            p.subcategory.name if p.subcategory else '',
            p.description or '', p.tags or '',
            p.created_by.username if p.created_by else '',
            p.created_at.strftime('%Y-%m-%d %H:%M:%S') if p.created_at else '',
        ])
        count += 1

    AuditService.log_export(request.user, 'products', record_count=count, request=request)
    return response
