import datetime

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from aps.forms import ProductCodeSettingsForm
from aps.models import AuditLog, Product, ProductCodeSettings
from aps.services.audit import AuditService


from aps.permissions import can_manage_settings, permission_required

@login_required
@permission_required(can_manage_settings, 'You do not have permission to access settings.')
def settings_view(request):
    code_settings = ProductCodeSettings.load(user=request.user)
    code_form = ProductCodeSettingsForm(instance=code_settings)

    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        if form_type == 'product_code_settings':
            code_form = ProductCodeSettingsForm(request.POST, instance=code_settings)
            if code_form.is_valid():
                code_form.save()
                AuditService.log(
                    request.user, AuditLog.ACTION_SETTINGS_CHANGED,
                    object_type='product_code_settings', object_id=code_settings.pk,
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
        asin_code__isnull=True, is_deleted=False, created_by=request.user
    ).count()

    return render(request, 'aps/settings.html', {
        'page_title': 'Settings',
        'active_menu': 'settings',
        'code_form': code_form,
        'code_settings': code_settings,
        'preview_code': preview_code,
        'products_without_code': products_without_code,
    })


@login_required
@require_POST
@permission_required(can_manage_settings, 'You do not have permission to access settings.')
def migrate_product_codes(request):
    products = Product.objects.filter(
        asin_code__isnull=True, is_deleted=False, created_by=request.user
    ).order_by('created_at')
    count = 0
    for p in products:
        p.asin_code = Product._generate_asin_code(user=request.user)
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
