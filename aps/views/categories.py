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


@business_user_required
def category_edit_api(request):
    from django.shortcuts import get_object_or_404
    if request.method == 'POST':
        category_id = request.POST.get('category_id')
        category = get_object_or_404(Category, pk=category_id, created_by=request.user)
        form = CategoryForm(request.POST, instance=category, user=request.user)
        if form.is_valid():
            form.save()
            AuditService.log(
                request.user, AuditLog.ACTION_CATEGORY_UPDATED,
                object_type='category', object_id=category.pk,
                object_repr=category.name, request=request,
            )
            messages.success(request, 'Category updated.')
        else:
            messages.error(request, form.errors.as_text() or 'Failed to update category.')
    return redirect('categories_list')


@business_user_required
def subcategory_edit_api(request):
    from django.shortcuts import get_object_or_404
    from aps.models import SubCategory
    if request.method == 'POST':
        subcategory_id = request.POST.get('subcategory_id')
        subcategory = get_object_or_404(SubCategory, pk=subcategory_id, category__created_by=request.user)
        form = SubCategoryForm(request.POST, instance=subcategory, user=request.user)
        if form.is_valid():
            form.save()
            AuditService.log(
                request.user, AuditLog.ACTION_SUBCATEGORY_UPDATED,
                object_type='subcategory', object_id=subcategory.pk,
                object_repr=str(subcategory), request=request,
            )
            messages.success(request, 'Subcategory updated.')
        else:
            messages.error(request, form.errors.as_text() or 'Failed to update subcategory.')
    return redirect('categories_list')
