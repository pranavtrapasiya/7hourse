"""
Administrator-only user monitoring views.
Provides user-centric monitoring with separate sections for products, locations, orders, and activity.
"""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Sum, Q
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse

from aps.models import (
    AuditLog, Category, Product, ProductCodeSettings,
    WarehouseInventory, Order, User, UserProfile,
)
from aps.permissions import admin_required
from aps.services.analytics import AnalyticsService


@admin_required
def users_list(request):
    """Show all approved users in responsive card layout."""
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')

    # Get all non-superuser users
    users_qs = User.objects.filter(is_superuser=False).select_related('profile')

    # Apply search filter
    if search_query:
        users_qs = users_qs.filter(
            username__icontains=search_query
        ) | users_qs.filter(
            email__icontains=search_query
        ) | users_qs.filter(
            first_name__icontains=search_query
        ) | users_qs.filter(
            last_name__icontains=search_query
        )

    # Apply status filter
    if status_filter == 'active':
        users_qs = users_qs.filter(is_active=True)
    elif status_filter == 'inactive':
        users_qs = users_qs.filter(is_active=False)

    # Annotate with counts
    users_qs = users_qs.annotate(
        total_products=Count('products_created', distinct=True),
        total_inventory=Count('inventory_created', distinct=True),
        total_orders=Count('orders', distinct=True),
    )

    # Get last login for each user
    users_data = []
    for user in users_qs:
        last_login = AuditLog.objects.filter(
            user=user, action=AuditLog.ACTION_LOGIN
        ).order_by('-created_at').first()
        users_data.append({
            'user': user,
            'profile': getattr(user, 'profile', None),
            'total_products': user.total_products,
            'total_inventory': user.total_inventory,
            'total_orders': user.total_orders,
            'last_login': last_login.created_at if last_login else None,
        })

    # Pagination
    paginator = Paginator(users_data, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'aps/users_list.html', {
        'page_title': 'Users',
        'active_menu': 'users',
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
    })


@admin_required
def user_details(request, user_id):
    """Show user profile with tabs/sections for Products, Locations, Orders, Activity."""
    target_user = get_object_or_404(User, pk=user_id, is_superuser=False)
    profile, _ = UserProfile.objects.get_or_create(user=target_user)

    # Get comprehensive stats
    stats = AnalyticsService.user_comprehensive_stats(target_user)

    # Get last login
    last_login = AuditLog.objects.filter(
        user=target_user, action=AuditLog.ACTION_LOGIN
    ).order_by('-created_at').first()

    # Get user's categories and settings for admin monitoring
    user_categories = Category.objects.filter(
        created_by=target_user
    ).prefetch_related('subcategories').order_by('name')
    user_code_settings = ProductCodeSettings.load(user=target_user)

    return render(request, 'aps/user_details.html', {
        'page_title': f'User: {target_user.username}',
        'active_menu': 'users',
        'target_user': target_user,
        'profile': profile,
        'stats': stats,
        'last_login': last_login.created_at if last_login else None,
        'user_categories': user_categories,
        'user_code_settings': user_code_settings,
    })


@admin_required
def user_products(request, user_id):
    """Show only products created by the selected user."""
    target_user = get_object_or_404(User, pk=user_id, is_superuser=False)

    # Get products created by this user
    products_qs = Product.objects.filter(
        created_by=target_user, is_deleted=False
    ).select_related('category', 'subcategory').order_by('-created_at')

    # Pagination
    paginator = Paginator(products_qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'aps/user_products.html', {
        'page_title': f'Products - {target_user.username}',
        'active_menu': 'users',
        'target_user': target_user,
        'page_obj': page_obj,
    })


@admin_required
def user_locations(request, user_id):
    """Show only locations created by the selected user."""
    target_user = get_object_or_404(User, pk=user_id, is_superuser=False)

    # Get inventory entries created by this user
    locations_qs = WarehouseInventory.objects.filter(
        created_by=target_user
    ).select_related('product').order_by('-created_at')

    # Pagination
    paginator = Paginator(locations_qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'aps/user_locations.html', {
        'page_title': f'Locations - {target_user.username}',
        'active_menu': 'users',
        'target_user': target_user,
        'page_obj': page_obj,
    })


@admin_required
def user_orders(request, user_id):
    """Show only orders created by the selected user."""
    target_user = get_object_or_404(User, pk=user_id, is_superuser=False)

    # Get orders created by this user
    orders_qs = Order.objects.filter(
        created_by=target_user
    ).select_related('product', 'location').order_by('-created_at')

    # Pagination
    paginator = Paginator(orders_qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'aps/user_orders.html', {
        'page_title': f'Orders - {target_user.username}',
        'active_menu': 'users',
        'target_user': target_user,
        'page_obj': page_obj,
    })


@admin_required
def user_activity(request, user_id):
    """Show complete audit trail for the selected user."""
    target_user = get_object_or_404(User, pk=user_id, is_superuser=False)

    # Get activity for this user
    activity_qs = AuditLog.objects.filter(
        Q(user=target_user) | Q(object_type='user', object_id=target_user.pk)
    ).select_related('user').order_by('-created_at')

    # Pagination
    paginator = Paginator(activity_qs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'aps/user_activity.html', {
        'page_title': f'Activity - {target_user.username}',
        'active_menu': 'users',
        'target_user': target_user,
        'page_obj': page_obj,
    })
