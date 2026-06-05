import csv
import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Case, When, Value, IntegerField
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.utils.html import escape

from .models import (
    Category, SubCategory, Product,
    WarehouseInventory, CartonImage, InventoryProductImage, InventoryVideo,
    ProductCodeSettings, ProductCodeSequence,
    Order,
)
from .forms import (
    CategoryForm, SubCategoryForm,
    ProductForm, WarehouseInventoryForm,
    ProductCodeSettingsForm, OrderForm,
)

MAX_CARTON_IMAGES = 2
MAX_PRODUCT_IMAGES = 5


# ─── Dashboard ────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    total_products = Product.objects.filter(is_deleted=False).count()
    total_categories = Category.objects.count()
    total_subcategories = SubCategory.objects.count()
    total_inventory = WarehouseInventory.objects.count()
    recent_products = Product.objects.filter(is_deleted=False).select_related('category', 'subcategory')[:10]

    context = {
        'page_title': 'Dashboard',
        'active_menu': 'dashboard',
        'total_products': total_products,
        'total_categories': total_categories,
        'total_subcategories': total_subcategories,
        'total_inventory': total_inventory,
        'recent_products': recent_products,
    }
    return render(request, 'aps/dashboard.html', context)


# ─── Settings ─────────────────────────────────────────────────────────────────

@login_required
def settings_view(request):
    cat_form = CategoryForm()
    subcat_form = SubCategoryForm()
    code_settings = ProductCodeSettings.load()
    code_form = ProductCodeSettingsForm(instance=code_settings)

    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        if form_type == 'category':
            cat_form = CategoryForm(request.POST)
            if cat_form.is_valid():
                cat_form.save()
                messages.success(request, 'Category added.')
                return redirect('settings')
            messages.error(request, 'Fix the errors below.')
        elif form_type == 'subcategory':
            subcat_form = SubCategoryForm(request.POST)
            if subcat_form.is_valid():
                subcat_form.save()
                messages.success(request, 'Subcategory added.')
                return redirect('settings')
            messages.error(request, 'Fix the errors below.')
        elif form_type == 'product_code_settings':
            code_form = ProductCodeSettingsForm(request.POST, instance=code_settings)
            if code_form.is_valid():
                code_form.save()
                messages.success(request, 'Product code settings saved.')
                return redirect('settings')
            messages.error(request, 'Fix the errors below.')

    # Generate preview code
    now = datetime.datetime.now()
    preview_seq = '1'.zfill(code_settings.sequence_length)
    preview_code = code_settings.prefix_format.replace('{YEAR}', str(now.year))
    preview_code = preview_code.replace('{MONTH}', now.strftime('%b').upper())
    preview_code = preview_code.replace('{SEQ}', preview_seq)
    products_without_code = Product.objects.filter(
        asin_code__isnull=True, is_deleted=False
    ).count()

    categories = Category.objects.prefetch_related('subcategories').order_by('name')
    context = {
        'page_title': 'Settings',
        'active_menu': 'settings',
        'cat_form': cat_form,
        'subcat_form': subcat_form,
        'code_form': code_form,
        'code_settings': code_settings,
        'preview_code': preview_code,
        'products_without_code': products_without_code,
        'categories': categories,
    }
    return render(request, 'aps/settings.html', context)


# ─── Product CRUD ─────────────────────────────────────────────────────────────

@login_required
def product_add(request):
    form = ProductForm()
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Product "{product.product_name}" added. ASIN: {product.asin_code}')
            return redirect('product_detail', pk=product.pk)
        messages.error(request, 'Fix the form errors below.')

    context = {
        'page_title': 'Add Product',
        'active_menu': 'add_product',
        'product_form': form,
    }
    return render(request, 'aps/product_add.html', context)


@login_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk, is_deleted=False)
    form = ProductForm(instance=product)

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Product "{product.product_name}" updated.')
            return redirect('product_detail', pk=product.pk)
        messages.error(request, 'Fix the form errors.')

    context = {
        'page_title': 'Edit Product',
        'active_menu': 'product_list',
        'product': product,
        'product_form': form,
        'is_edit': True,
    }
    return render(request, 'aps/product_add.html', context)


@login_required
def product_delete(request, pk):
    """Soft-delete a product instead of hard delete for data protection."""
    product = get_object_or_404(Product, pk=pk, is_deleted=False)
    if request.method == 'POST':
        name = product.product_name
        product.soft_delete()
        messages.success(request, f'Product "{name}" moved to trash.')
        return redirect('product_list')
    return redirect('product_detail', pk=pk)


@login_required
def product_restore(request, pk):
    """Restore a soft-deleted product."""
    product = get_object_or_404(Product, pk=pk, is_deleted=True)
    if request.method == 'POST':
        product.restore()
        messages.success(request, f'Product "{product.product_name}" restored.')
        return redirect('product_detail', pk=pk)
    return redirect('deleted_products')


@login_required
def product_permanent_delete(request, pk):
    """Permanently delete a product (only from trash)."""
    product = get_object_or_404(Product, pk=pk, is_deleted=True)
    if request.method == 'POST':
        name = product.product_name
        if product.main_image:
            product.main_image.delete(save=False)
        product.delete()
        messages.success(request, f'Product "{name}" permanently deleted.')
        return redirect('deleted_products')
    return redirect('deleted_products')


@login_required
def deleted_products(request):
    """View all soft-deleted products with restore option."""
    qs = Product.objects.filter(is_deleted=True).select_related(
        'category', 'subcategory'
    ).order_by('-deleted_at')

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_title': 'Deleted Products',
        'active_menu': 'product_list',
        'page_obj': page_obj,
    }
    return render(request, 'aps/deleted_products.html', context)


# ─── Product List ─────────────────────────────────────────────────────────────

@login_required
def product_list(request):
    qs = Product.objects.filter(is_deleted=False).select_related('category', 'subcategory')

    search_query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    subcategory_id = request.GET.get('subcategory', '')
    sort = request.GET.get('sort', '-created_at')

    if search_query:
        qs = qs.filter(
            product_name__icontains=search_query
        )
    if category_id:
        qs = qs.filter(category_id=category_id)
    if subcategory_id:
        qs = qs.filter(subcategory_id=subcategory_id)

    sort_map = {
        '-created_at': '-created_at', 'created_at': 'created_at',
        'product_name': 'product_name', '-product_name': '-product_name',
    }
    qs = qs.order_by(sort_map.get(sort, '-created_at'))

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_title': 'Products',
        'active_menu': 'product_list',
        'page_obj': page_obj,
        'search_query': search_query,
        'category_id': category_id,
        'subcategory_id': subcategory_id,
        'sort': sort,
        'categories': Category.objects.all(),
        'subcategories': SubCategory.objects.filter(category_id=category_id) if category_id else SubCategory.objects.all(),
    }
    return render(request, 'aps/product_list.html', context)


# ─── Product Detail ───────────────────────────────────────────────────────────

@login_required
def product_detail(request, pk):
    product = get_object_or_404(
        Product.objects.select_related('category', 'subcategory'),
        pk=pk
    )
    inventory_entries = product.inventory_entries.prefetch_related(
        'carton_images', 'product_images', 'video'
    ).order_by('-created_at')

    context = {
        'page_title': product.product_name,
        'active_menu': 'product_list',
        'product': product,
        'inventory_entries': inventory_entries,
        'latest_inventory': inventory_entries.first(),
    }
    return render(request, 'aps/product_detail.html', context)


# ─── Location / Warehouse Inventory ───────────────────────────────────────────

@login_required
def location_view(request):
    """
    Step 1: Search products.
    Step 2: Select a product (checkbox / link).
    Step 3: Show WarehouseInventory form dynamically (AJAX or GET param).
    Step 4: Save inventory entry with media.
    """
    search_query = request.GET.get('q', '').strip()
    selected_product_id = request.GET.get('product_id', '').strip()
    selected_product = None
    inv_form = WarehouseInventoryForm()
    existing_entries = []

    # Product search results
    search_results = []
    if search_query:
        search_results = list(
            Product.objects.filter(
                product_name__icontains=search_query,
                is_deleted=False
            ).select_related('category', 'subcategory')[:20]
        )

    # Load selected product
    if selected_product_id:
        selected_product = get_object_or_404(
            Product.objects.select_related('category', 'subcategory'),
            pk=selected_product_id,
            is_deleted=False
        )
        existing_entries = selected_product.inventory_entries.prefetch_related(
            'carton_images', 'product_images'
        ).order_by('-created_at')

    # Handle form submission
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        selected_product = get_object_or_404(Product, pk=product_id, is_deleted=False)
        inv_form = WarehouseInventoryForm(request.POST)

        if inv_form.is_valid():
            inventory = inv_form.save(commit=False)
            inventory.product = selected_product
            inventory.save()

            # Carton images (max 2)
            carton_files = request.FILES.getlist('carton_images')
            current_carton = 0
            for f in carton_files:
                if current_carton >= MAX_CARTON_IMAGES:
                    messages.warning(request, f'Max {MAX_CARTON_IMAGES} carton images allowed. Some skipped.')
                    break
                CartonImage.objects.create(inventory=inventory, image=f)
                current_carton += 1

            # Product images (max 5)
            product_files = request.FILES.getlist('product_images')
            current_prod = 0
            for f in product_files:
                if current_prod >= MAX_PRODUCT_IMAGES:
                    messages.warning(request, f'Max {MAX_PRODUCT_IMAGES} product images allowed. Some skipped.')
                    break
                InventoryProductImage.objects.create(inventory=inventory, image=f)
                current_prod += 1

            # Video (1 only)
            video_file = request.FILES.get('video')
            if video_file:
                InventoryVideo.objects.create(inventory=inventory, video=video_file)

            messages.success(request, f'Inventory entry saved for "{selected_product.product_name}".')
            return redirect(f'{request.path}?product_id={selected_product.pk}')
        else:
            messages.error(request, 'Please fix the form errors.')
            existing_entries = selected_product.inventory_entries.prefetch_related(
                'carton_images', 'product_images'
            ).order_by('-created_at')

    context = {
        'page_title': 'Warehouse Inventory',
        'active_menu': 'location',
        'search_query': search_query,
        'search_results': search_results,
        'selected_product': selected_product,
        'selected_product_id': selected_product_id,
        'inv_form': inv_form,
        'existing_entries': existing_entries,
        'max_carton': MAX_CARTON_IMAGES,
        'max_product_images': MAX_PRODUCT_IMAGES,
    }
    return render(request, 'aps/location.html', context)


@login_required
def delete_inventory_entry(request, pk):
    """Delete a single inventory entry (not the product itself)."""
    entry = get_object_or_404(WarehouseInventory, pk=pk)
    product_id = entry.product.pk
    if request.method == 'POST':
        entry.delete()
        messages.success(request, 'Inventory entry deleted.')
    return redirect(f'/location/?product_id={product_id}')


# ─── AJAX ─────────────────────────────────────────────────────────────────────

@login_required
def ajax_subcategories(request):
    category_id = request.GET.get('category_id')
    subcategories = []
    if category_id:
        subcategories = list(
            SubCategory.objects.filter(category_id=category_id).values('id', 'name')
        )
    return JsonResponse({'subcategories': subcategories})


@login_required
def ajax_product_search(request):
    """Returns JSON results for live product search on location page."""
    q = request.GET.get('q', '').strip()
    results = []
    if len(q) >= 1:
        qs = Product.objects.filter(
            is_deleted=False
        ).select_related('category', 'subcategory').filter(
            product_name__icontains=q
        ).annotate(
            search_priority=Case(
                When(product_name__istartswith=q, then=Value(1)),
                default=Value(2),
                output_field=IntegerField()
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


@login_required
def ajax_preview_code(request):
    """Return a live preview of the product code format."""
    fmt = request.GET.get('format', '{YEAR}{MONTH}{SEQ}')
    try:
        seq_len = min(max(int(request.GET.get('seq_len', 4)), 1), 10)
    except (ValueError, TypeError):
        seq_len = 4
    now = datetime.datetime.now()
    preview = fmt.replace('{YEAR}', str(now.year))
    preview = preview.replace('{MONTH}', now.strftime('%b').upper())
    preview = preview.replace('{SEQ}', '1'.zfill(seq_len))
    return JsonResponse({'preview': preview})


@login_required
@require_POST
def migrate_product_codes(request):
    """Generate codes for all existing products that don't have one."""
    products = Product.objects.filter(
        asin_code__isnull=True, is_deleted=False
    ).order_by('created_at')
    count = 0
    for p in products:
        p.asin_code = Product._generate_asin_code()
        p.save(update_fields=['asin_code'])
        count += 1
    messages.success(request, f'Generated codes for {count} product(s).')
    return redirect('settings')


def logout_view(request):
    from django.contrib.auth import logout as django_logout
    django_logout(request)
    return redirect('login')


# ─── API Search (Real-time, Google-like) ──────────────────────────────────────

@login_required
def api_product_search(request):
    """
    Optimized real-time API search view with multi-field search.
    GET /api/products/search?q=query&page=1
    Searches: product_name, product_code, category, subcategory, description, tags
    """
    q = request.GET.get('q', '').strip()
    page_num = request.GET.get('page', 1)

    if not q:
        return JsonResponse({
            'suggestions': [],
            'results': [],
            'total': 0
        })

    # Multi-field search with priority ranking
    # Priority 1: product_name starts with query
    # Priority 2: product_name contains query
    # Priority 3: other fields contain query
    qs = Product.objects.filter(is_deleted=False).select_related(
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
            output_field=IntegerField()
        )
    ).order_by('search_priority', 'product_name').distinct()

    total_count = qs.count()

    # Limit suggestions to 10 results
    suggestions_qs = qs[:10]
    suggestions = []
    for p in suggestions_qs:
        suggestions.append({
            'id': p.id,
            'product_name': p.product_name,
            'product_code': p.asin_code or '',
            'asin_code': p.asin_code or '',
            'category': p.category.name if p.category else '',
            'subcategory': p.subcategory.name if p.subcategory else '',
            'image_url': p.main_image.url if p.main_image else '',
            'has_image': bool(p.main_image),
        })

    # Paginate full results
    paginator = Paginator(qs, 24)
    try:
        page_obj = paginator.page(page_num)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    results = []
    for p in page_obj:
        results.append({
            'id': p.id,
            'product_name': p.product_name,
            'product_code': p.asin_code or '',
            'asin_code': p.asin_code or '',
            'category': p.category.name if p.category else '',
            'subcategory': p.subcategory.name if p.subcategory else '',
            'image_url': p.main_image.url if p.main_image else '',
            'has_image': bool(p.main_image),
        })

    return JsonResponse({
        'suggestions': suggestions,
        'results': results,
        'total': total_count
    })


# ─── Export Products CSV ──────────────────────────────────────────────────────

@login_required
def export_products_csv(request):
    """Export all active products to CSV for backup/data protection."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="products_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    )
    response.write('\ufeff')  # BOM for Excel compatibility

    writer = csv.writer(response)
    writer.writerow([
        'ID', 'Product Name', 'ASIN Code', 'SH Code',
        'Category', 'Subcategory', 'Description', 'Tags', 'Created At'
    ])

    products = Product.objects.filter(is_deleted=False).select_related(
        'category', 'subcategory'
    ).order_by('created_at').iterator(chunk_size=500)

    for p in products:
        writer.writerow([
            p.id,
            p.product_name,
            p.asin_code or '',
            p.sh_code or '',
            p.category.name if p.category else '',
            p.subcategory.name if p.subcategory else '',
            p.description or '',
            p.tags or '',
            p.created_at.strftime('%Y-%m-%d %H:%M:%S') if p.created_at else '',
        ])

    return response


# ─── Order Module ─────────────────────────────────────────────────────────────

@login_required
def order_create(request):
    """Order creation page: Search product → select location → fill order form."""
    context = {
        'page_title': 'New Order',
        'active_menu': 'order',
    }
    return render(request, 'aps/order_create.html', context)


@login_required
def order_list(request):
    """List all orders with search, filter, and pagination."""
    qs = Order.objects.select_related('product', 'location', 'created_by').all()

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

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_title': 'Orders',
        'active_menu': 'order_list',
        'page_obj': page_obj,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
        'sort': sort,
        'total_orders': Order.objects.count(),
    }
    return render(request, 'aps/order_list.html', context)


@login_required
def order_detail_api(request, pk):
    """Return order detail as JSON for modal view."""
    order = get_object_or_404(
        Order.objects.select_related('product', 'location', 'created_by'),
        pk=pk
    )
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
    })


@login_required
def order_save_api(request):
    """AJAX endpoint to save a new order."""
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
        order.save()
        return JsonResponse({
            'success': True,
            'order_id': order.pk,
            'message': f'Order #{order.pk} saved successfully.'
        })
    else:
        errors = {field: errs[0] for field, errs in form.errors.items()}
        return JsonResponse({'success': False, 'errors': errors}, status=400)


@login_required
def order_edit(request, pk):
    """AJAX endpoint to edit an existing order."""
    order = get_object_or_404(Order, pk=pk)

    if request.method == 'GET':
        # Return order data for editing
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
        # Keep original product/location
        order.save()
        return JsonResponse({
            'success': True,
            'order_id': order.pk,
            'message': f'Order #{order.pk} updated successfully.'
        })
    else:
        errors = {field: errs[0] for field, errs in form.errors.items()}
        return JsonResponse({'success': False, 'errors': errors}, status=400)


@login_required
@require_POST
def order_delete(request, pk):
    """Delete an order."""
    order = get_object_or_404(Order, pk=pk)
    order_id = order.pk
    order.delete()
    return JsonResponse({'success': True, 'message': f'Order #{order_id} deleted.'})


@login_required
def ajax_order_locations(request):
    """Return all warehouse locations for a product as JSON."""
    product_id = request.GET.get('product_id')
    if not product_id:
        return JsonResponse({'locations': []})

    entries = WarehouseInventory.objects.filter(
        product_id=product_id
    ).order_by('-created_at')

    locations = []
    for e in entries:
        locations.append({
            'id': e.pk,
            'location_number': e.location_number or '—',
            'price': str(e.price),
            'cbm': str(e.cbm),
            'carton_piece': e.carton_piece,
            'remark': e.remark or '',
            'created_at': e.created_at.strftime('%d %b %Y') if e.created_at else '',
        })

    return JsonResponse({'locations': locations})