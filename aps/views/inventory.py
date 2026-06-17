from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404

from aps.forms import WarehouseInventoryForm
from aps.models import (
    AuditLog, CartonImage, InventoryProductImage, InventoryVideo,
    Product, WarehouseInventory,
)
from aps.permissions import (
    business_user_required, can_delete_inventory, permission_required,
    filter_products_own, filter_inventory_own, get_product_for_user,
    filter_inventory_for_user,
)
from aps.services.audit import AuditService

MAX_CARTON_IMAGES = 2
MAX_PRODUCT_IMAGES = 5


@business_user_required
def location_view(request):
    search_query = request.GET.get('q', '').strip()
    selected_product_id = request.GET.get('product_id', '').strip()
    selected_product = None
    inv_form = WarehouseInventoryForm()
    existing_entries = []
    search_results = []

    if search_query:
        search_results = list(
            filter_products_own(request.user).filter(
                product_name__icontains=search_query, is_deleted=False,
            ).select_related('category', 'subcategory')[:20]
        )

    if selected_product_id:
        selected_product = get_object_or_404(
            filter_products_own(request.user).select_related('category', 'subcategory'),
            pk=selected_product_id, is_deleted=False,
        )
        existing_entries = filter_inventory_own(request.user, selected_product.inventory_entries).select_related(
            'created_by'
        ).prefetch_related('carton_images', 'product_images').order_by('-created_at')

    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        selected_product = get_object_or_404(filter_products_own(request.user), pk=product_id, is_deleted=False)
        inv_form = WarehouseInventoryForm(request.POST)

        if inv_form.is_valid():
            inventory = inv_form.save(commit=False)
            inventory.product = selected_product
            inventory.created_by = request.user
            inventory.updated_by = request.user
            inventory.save()

            from django.core.exceptions import ValidationError
            
            for f in request.FILES.getlist('carton_images')[:MAX_CARTON_IMAGES]:
                img = CartonImage(inventory=inventory, image=f, uploaded_by=request.user)
                try:
                    img.full_clean()
                    img.save()
                except ValidationError as e:
                    messages.error(request, f'Validation error for carton image {f.name}: {e.messages}')
            if len(request.FILES.getlist('carton_images')) > MAX_CARTON_IMAGES:
                messages.warning(request, f'Max {MAX_CARTON_IMAGES} QR code images allowed. Some skipped.')

            for f in request.FILES.getlist('product_images')[:MAX_PRODUCT_IMAGES]:
                img = InventoryProductImage(inventory=inventory, image=f, uploaded_by=request.user)
                try:
                    img.full_clean()
                    img.save()
                except ValidationError as e:
                    messages.error(request, f'Validation error for product image {f.name}: {e.messages}')
            if len(request.FILES.getlist('product_images')) > MAX_PRODUCT_IMAGES:
                messages.warning(request, f'Max {MAX_PRODUCT_IMAGES} product images allowed. Some skipped.')

            video_file = request.FILES.get('video')
            if video_file:
                vid = InventoryVideo(inventory=inventory, video=video_file, uploaded_by=request.user)
                try:
                    vid.full_clean()
                    vid.save()
                except ValidationError as e:
                    messages.error(request, f'Validation error for video: {e.messages}')

            AuditService.log_inventory(
                request.user, AuditLog.ACTION_INVENTORY_CREATED, inventory,
                details={'location': inventory.location_number}, request=request,
            )
            messages.success(request, f'Inventory entry saved for "{selected_product.product_name}".')
            return redirect(f'{request.path}?product_id={selected_product.pk}')
        messages.error(request, 'Please fix the form errors.')
        existing_entries = filter_inventory_own(request.user, selected_product.inventory_entries).prefetch_related(
            'carton_images', 'product_images'
        ).order_by('-created_at')

    return render(request, 'aps/location.html', {
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
    })


@permission_required(can_delete_inventory, 'Only administrators can delete inventory entries.')
def delete_inventory_entry(request, pk):
    entry = get_object_or_404(filter_inventory_for_user(request.user), pk=pk)
    product_id = entry.product.pk
    if request.method == 'POST':
        AuditService.log_inventory(
            request.user, AuditLog.ACTION_INVENTORY_DELETED, entry, request=request,
        )
        entry.delete()
        messages.success(request, 'Inventory entry deleted.')
    return redirect(f'/location/?product_id={product_id}')


@business_user_required
def edit_inventory_price(request, pk):
    entry = get_object_or_404(filter_inventory_for_user(request.user), pk=pk)
    product_id = entry.product.pk
    if request.method == 'POST':
        price = request.POST.get('price')
        if price is not None:
            try:
                entry.price = price
                entry.save()
                AuditService.log_inventory(
                    request.user, AuditLog.ACTION_INVENTORY_UPDATED, entry,
                    details={'price': str(entry.price), 'action': 'edit_price'},
                    request=request,
                )
                messages.success(request, 'Inventory price updated.')
            except (ValueError, TypeError):
                messages.error(request, 'Invalid price format.')
    return redirect(f'/location/?product_id={product_id}')
