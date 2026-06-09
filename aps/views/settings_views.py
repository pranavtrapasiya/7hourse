import datetime

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from aps.forms import CategoryForm, SubCategoryForm, ProductCodeSettingsForm
from aps.models import AuditLog, Category, Product, ProductCodeSettings
from aps.permissions import can_manage_settings, permission_required
from aps.services.audit import AuditService


@permission_required(can_manage_settings, 'Only administrators can access system settings.')
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
                category = cat_form.save()
                AuditService.log(
                    request.user, AuditLog.ACTION_CATEGORY_CREATED,
                    object_type='category', object_id=category.pk,
                    object_repr=category.name, request=request,
                )
                messages.success(request, 'Category added.')
                return redirect('settings')
            messages.error(request, 'Fix the errors below.')
        elif form_type == 'subcategory':
            subcat_form = SubCategoryForm(request.POST)
            if subcat_form.is_valid():
                subcat = subcat_form.save()
                AuditService.log(
                    request.user, AuditLog.ACTION_SUBCATEGORY_CREATED,
                    object_type='subcategory', object_id=subcat.pk,
                    object_repr=str(subcat), request=request,
                )
                messages.success(request, 'Subcategory added.')
                return redirect('settings')
            messages.error(request, 'Fix the errors below.')
        elif form_type == 'product_code_settings':
            code_form = ProductCodeSettingsForm(request.POST, instance=code_settings)
            if code_form.is_valid():
                code_form.save()
                AuditService.log(
                    request.user, AuditLog.ACTION_SETTINGS_CHANGED,
                    object_type='product_code_settings', object_id=1,
                    object_repr='Product Code Settings', request=request,
                )
                messages.success(request, 'Product code settings saved.')
                return redirect('settings')
            messages.error(request, 'Fix the errors below.')

    now = datetime.datetime.now()
    preview_seq = '1'.zfill(code_settings.sequence_length)
    preview_code = code_settings.prefix_format.replace('{YEAR}', str(now.year))
    preview_code = preview_code.replace('{MONTH}', now.strftime('%b').upper())
    preview_code = preview_code.replace('{SEQ}', preview_seq)
    products_without_code = Product.objects.filter(
        asin_code__isnull=True, is_deleted=False
    ).count()

    categories = Category.objects.prefetch_related('subcategories').order_by('name')
    return render(request, 'aps/settings.html', {
        'page_title': 'Settings',
        'active_menu': 'settings',
        'cat_form': cat_form,
        'subcat_form': subcat_form,
        'code_form': code_form,
        'code_settings': code_settings,
        'preview_code': preview_code,
        'products_without_code': products_without_code,
        'categories': categories,
    })


@permission_required(can_manage_settings, 'Only administrators can migrate product codes.')
@require_POST
def migrate_product_codes(request):
    products = Product.objects.filter(
        asin_code__isnull=True, is_deleted=False
    ).order_by('created_at')
    count = 0
    for p in products:
        p.asin_code = Product._generate_asin_code()
        p.save(update_fields=['asin_code'])
        count += 1
    AuditService.log(
        request.user, AuditLog.ACTION_SETTINGS_CHANGED,
        object_type='product_code_migration',
        object_repr=f'Migrated {count} product codes',
        details={'count': count},
        request=request,
    )
    messages.success(request, f'Generated codes for {count} product(s).')
    return redirect('settings')
