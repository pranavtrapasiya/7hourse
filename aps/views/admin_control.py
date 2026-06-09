from django.contrib.auth.models import User
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST

from aps.models import AuditLog, UserProfile
from aps.permissions import admin_required
from aps.services.analytics import AnalyticsService
from aps.services.audit import AuditService
from aps.services.dashboard import DashboardService


@admin_required
def admin_control_center(request):
    stats = DashboardService.company_stats()
    user_performance = AnalyticsService.user_performance()
    order_analytics = AnalyticsService.order_analytics()
    inventory_analytics = AnalyticsService.inventory_analytics()
    activity_feed = AnalyticsService.activity_feed(limit=25)

    return render(request, 'aps/admin_control_center.html', {
        'page_title': 'Admin Control Center',
        'active_menu': 'admin_control',
        **stats,
        'user_performance': user_performance,
        'order_analytics': order_analytics,
        'inventory_analytics': inventory_analytics,
        'activity_feed': activity_feed,
    })


@admin_required
def admin_users(request):
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'all')

    qs = User.objects.filter(is_superuser=False).select_related('profile')
    if status_filter == 'active':
        qs = qs.filter(is_active=True)
    elif status_filter == 'inactive':
        qs = qs.filter(is_active=False)
    elif status_filter == 'staff':
        qs = qs.filter(is_staff=True)

    if search_query:
        qs = qs.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query)
        )

    page_obj = Paginator(qs.order_by('-date_joined'), 25).get_page(request.GET.get('page'))

    return render(request, 'aps/admin_users.html', {
        'page_title': 'User Management',
        'active_menu': 'admin_control',
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
    })


@admin_required
def admin_user_detail(request, user_id):
    target = get_object_or_404(User, pk=user_id, is_superuser=False)
    profile, _ = UserProfile.objects.get_or_create(user=target)
    activity = AnalyticsService.user_activity(target, limit=30)
    login_history = AnalyticsService.user_login_history(target, limit=20)
    export_history = AnalyticsService.user_export_history(target, limit=20)
    approval_history = AnalyticsService.user_approval_history(target)
    comprehensive_stats = AnalyticsService.user_comprehensive_stats(target)
    performance = AnalyticsService.user_performance(limit=100)
    user_perf = next((p for p in performance if p['user'].pk == target.pk), None)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'toggle_active':
            target.is_active = not target.is_active
            target.save(update_fields=['is_active'])
            audit_action = (
                AuditLog.ACTION_USER_ACTIVATED if target.is_active
                else AuditLog.ACTION_USER_DEACTIVATED
            )
            AuditService.log_user_action(
                request.user, audit_action, target, request=request,
            )
            messages.success(request, f'User "{target.username}" status updated.')
            return redirect('admin_user_detail', user_id=target.pk)
        elif action == 'toggle_staff':
            target.is_staff = not target.is_staff
            target.save(update_fields=['is_staff'])
            AuditService.log(
                request.user, AuditLog.ACTION_PERMISSION_CHANGED,
                object_type='user', object_id=target.pk,
                object_repr=target.username,
                details={'is_staff': target.is_staff},
                request=request,
            )
            messages.success(request, f'Administrator role updated for "{target.username}".')
            return redirect('admin_user_detail', user_id=target.pk)
        elif action == 'update_permissions':
            profile.can_export = request.POST.get('can_export') == 'on'
            profile.can_manage_all_orders = request.POST.get('can_manage_all_orders') == 'on'
            profile.can_manage_settings = request.POST.get('can_manage_settings') == 'on'
            profile.can_delete_products = request.POST.get('can_delete_products') == 'on'
            profile.can_delete_inventory = request.POST.get('can_delete_inventory') == 'on'
            profile.save()
            AuditService.log(
                request.user, AuditLog.ACTION_PERMISSION_CHANGED,
                object_type='user_profile', object_id=profile.pk,
                object_repr=target.username,
                details={
                    'can_export': profile.can_export,
                    'can_manage_all_orders': profile.can_manage_all_orders,
                    'can_manage_settings': profile.can_manage_settings,
                    'can_delete_products': profile.can_delete_products,
                    'can_delete_inventory': profile.can_delete_inventory,
                },
                request=request,
            )
            messages.success(request, f'Permissions updated for "{target.username}".')
            return redirect('admin_user_detail', user_id=target.pk)

    return render(request, 'aps/admin_user_detail.html', {
        'page_title': f'User: {target.username}',
        'active_menu': 'admin_control',
        'target_user': target,
        'profile': profile,
        'activity': activity,
        'login_history': login_history,
        'export_history': export_history,
        'approval_history': approval_history,
        'comprehensive_stats': comprehensive_stats,
        'user_perf': user_perf,
    })


@admin_required
def admin_audit_logs(request):
    action_filter = request.GET.get('action', '')
    user_filter = request.GET.get('user', '')
    qs = AuditLog.objects.select_related('user').order_by('-created_at')

    if action_filter:
        qs = qs.filter(action=action_filter)
    if user_filter:
        qs = qs.filter(user__username__icontains=user_filter)

    page_obj = Paginator(qs, 50).get_page(request.GET.get('page'))

    return render(request, 'aps/admin_audit_logs.html', {
        'page_title': 'Audit Logs',
        'active_menu': 'admin_control',
        'page_obj': page_obj,
        'action_filter': action_filter,
        'user_filter': user_filter,
        'action_choices': AuditLog.ACTION_CHOICES,
    })


@admin_required
def admin_user_activity_api(request, user_id):
    target = get_object_or_404(User, pk=user_id, is_superuser=False)
    page_num = request.GET.get('page', 1)
    qs = AnalyticsService.user_activity(target, limit=200)
    # Paginate the queryset properly
    activity_qs = AuditLog.objects.filter(user=target).select_related('user').order_by('-created_at')
    paginator = Paginator(activity_qs, 20)
    try:
        page_obj = paginator.page(page_num)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    logs = [{
        'id': log.pk,
        'action': log.get_action_display(),
        'object_repr': log.object_repr,
        'details': log.details,
        'created_at': log.created_at.strftime('%d %b %Y, %I:%M %p'),
    } for log in page_obj]

    return JsonResponse({
        'logs': logs,
        'total': paginator.count,
        'has_next': page_obj.has_next(),
        'current_page': page_obj.number,
    })
