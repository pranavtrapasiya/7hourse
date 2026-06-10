import json

from django.contrib.auth.models import User
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from aps.models import ApprovalLog, AuditLog
from aps.permissions import admin_required
from aps.services.audit import AuditService


@admin_required
def approval_requests(request):
    # IDs of users whose most recent approval action was a rejection
    rejected_user_ids = set(
        ApprovalLog.objects.filter(action='rejected')
        .values_list('target_user_id', flat=True).distinct()
    ) - set(
        # Exclude users who were later approved (re-approved after rejection)
        ApprovalLog.objects.filter(action='approved')
        .values_list('target_user_id', flat=True).distinct()
    )

    pending_users = User.objects.filter(
        is_active=False, is_superuser=False
    ).exclude(id__in=rejected_user_ids)
    approved_users = User.objects.filter(is_active=True, is_superuser=False)
    total_rejected = len(rejected_user_ids)

    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'pending')
    sort = request.GET.get('sort', '-date_joined')

    if status_filter == 'pending':
        qs = User.objects.filter(is_active=False, is_superuser=False).exclude(id__in=rejected_user_ids)
    elif status_filter == 'approved':
        qs = User.objects.filter(is_active=True, is_superuser=False)
    elif status_filter == 'rejected':
        qs = User.objects.filter(id__in=rejected_user_ids, is_active=False, is_superuser=False)
    else:
        qs = User.objects.filter(is_superuser=False)

    if search_query:
        qs = qs.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )

    sort_map = {
        '-date_joined': '-date_joined', 'date_joined': 'date_joined',
        'username': 'username', '-username': '-username',
    }
    qs = qs.order_by(sort_map.get(sort, '-date_joined'))
    recent_logs = ApprovalLog.objects.select_related(
        'target_user', 'performed_by'
    ).order_by('-created_at')[:20]

    from django.shortcuts import render
    return render(request, 'aps/approval_requests.html', {
        'page_title': 'User Approval Requests',
        'active_menu': 'approval_requests',
        'users': qs,
        'search_query': search_query,
        'status_filter': status_filter,
        'sort': sort,
        'pending_count': pending_users.count(),
        'approved_count': approved_users.count(),
        'rejected_count': total_rejected,
        'recent_logs': recent_logs,
    })


@admin_required
@require_POST
def approve_user_api(request, user_id):
    target_user = get_object_or_404(User, pk=user_id, is_superuser=False)
    note = request.POST.get('note', '').strip()

    if target_user.is_active:
        return JsonResponse({
            'success': False,
            'error': f'User "{target_user.username}" is already active.',
        }, status=400)

    target_user.is_active = True
    target_user.save(update_fields=['is_active'])

    ApprovalLog.objects.create(
        target_user=target_user, action='approved',
        performed_by=request.user, note=note,
    )
    AuditService.log_user_action(
        request.user, AuditLog.ACTION_USER_APPROVED, target_user, note=note, request=request,
    )

    return JsonResponse({
        'success': True,
        'message': f'User "{target_user.username}" has been approved and activated.',
        'user_id': target_user.pk,
    })


@admin_required
@require_POST
def reject_user_api(request, user_id):
    target_user = get_object_or_404(User, pk=user_id, is_superuser=False)
    note = request.POST.get('note', '').strip()

    target_user.is_active = False
    target_user.save(update_fields=['is_active'])

    ApprovalLog.objects.create(
        target_user=target_user, action='rejected',
        performed_by=request.user, note=note,
    )
    AuditService.log_user_action(
        request.user, AuditLog.ACTION_USER_REJECTED, target_user, note=note, request=request,
    )

    return JsonResponse({
        'success': True,
        'message': f'User "{target_user.username}" has been rejected.',
        'user_id': target_user.pk,
    })


@admin_required
@require_POST
def bulk_approve_api(request):
    try:
        body = json.loads(request.body)
        user_ids = body.get('user_ids', [])
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'error': 'Invalid request body.'}, status=400)

    if not user_ids:
        return JsonResponse({'success': False, 'error': 'No users selected.'}, status=400)

    users = User.objects.filter(pk__in=user_ids, is_active=False, is_superuser=False)
    count = 0
    for u in users:
        u.is_active = True
        u.save(update_fields=['is_active'])
        ApprovalLog.objects.create(
            target_user=u, action='approved',
            performed_by=request.user, note='Bulk approval',
        )
        AuditService.log_user_action(
            request.user, AuditLog.ACTION_USER_APPROVED, u, note='Bulk approval', request=request,
        )
        count += 1

    return JsonResponse({
        'success': True,
        'message': f'{count} user(s) approved successfully.',
        'count': count,
    })


@admin_required
@require_POST
def bulk_reject_api(request):
    try:
        body = json.loads(request.body)
        user_ids = body.get('user_ids', [])
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'error': 'Invalid request body.'}, status=400)

    if not user_ids:
        return JsonResponse({'success': False, 'error': 'No users selected.'}, status=400)

    users = User.objects.filter(pk__in=user_ids, is_superuser=False)
    count = 0
    for u in users:
        u.is_active = False
        u.save(update_fields=['is_active'])
        ApprovalLog.objects.create(
            target_user=u, action='rejected',
            performed_by=request.user, note='Bulk rejection',
        )
        AuditService.log_user_action(
            request.user, AuditLog.ACTION_USER_REJECTED, u, note='Bulk rejection', request=request,
        )
        count += 1

    return JsonResponse({
        'success': True,
        'message': f'{count} user(s) rejected successfully.',
        'count': count,
    })


@admin_required
def approval_history_api(request):
    page_num = request.GET.get('page', 1)
    qs = ApprovalLog.objects.select_related('target_user', 'performed_by').order_by('-created_at')
    paginator = Paginator(qs, 20)
    try:
        page_obj = paginator.page(page_num)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    logs = [{
        'id': log.pk,
        'target_username': log.target_user.username if log.target_user else '—',
        'target_email': log.target_user.email if log.target_user else '—',
        'action': log.action,
        'action_display': log.get_action_display(),
        'performed_by': log.performed_by.username if log.performed_by else '—',
        'note': log.note or '',
        'created_at': log.created_at.strftime('%d %b %Y, %I:%M %p'),
    } for log in page_obj]

    return JsonResponse({
        'logs': logs,
        'total': paginator.count,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
        'current_page': page_obj.number,
        'total_pages': paginator.num_pages,
    })
