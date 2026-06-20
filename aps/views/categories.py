from django.contrib import messages
from django.shortcuts import render, redirect

from aps.forms import CategoryForm, SubCategoryForm
from aps.models import AuditLog, Category
from aps.permissions import business_user_required
from aps.services.audit import AuditService


@business_user_required
def categories_list(request):
    cat_form = CategoryForm(user=request.user)
    subcat_form = SubCategoryForm(user=request.user)

    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        if form_type == 'category':
            cat_form = CategoryForm(request.POST, user=request.user)
            if cat_form.is_valid():
                category = cat_form.save(commit=False)
                category.created_by = request.user
                category.save()
                AuditService.log(
                    request.user, AuditLog.ACTION_CATEGORY_CREATED,
                    object_type='category', object_id=category.pk,
                    object_repr=category.name, request=request,
                )
                messages.success(request, 'Category added.')
                return redirect('categories_list')
            messages.error(request, 'Fix the errors below.')
        elif form_type == 'subcategory':
            subcat_form = SubCategoryForm(request.POST, user=request.user)
            if subcat_form.is_valid():
                subcat = subcat_form.save()
                AuditService.log(
                    request.user, AuditLog.ACTION_SUBCATEGORY_CREATED,
                    object_type='subcategory', object_id=subcat.pk,
                    object_repr=str(subcat), request=request,
                )
                messages.success(request, 'Subcategory added.')
                return redirect('categories_list')
            messages.error(request, 'Fix the errors below.')

    # Show only this user's categories
    categories = Category.objects.filter(
        created_by=request.user
    ).prefetch_related('subcategories').order_by('name')

    return render(request, 'aps/categories.html', {
        'page_title': 'Categories',
        'active_menu': 'categories',
        'cat_form': cat_form,
        'subcat_form': subcat_form,
        'categories': categories,
    })
