import json

from django.contrib.auth.models import User
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from django.utils import timezone

from aps.models import ApprovalLog, AuditLog, UserProfile
from aps.permissions import admin_required
from aps.services.audit import AuditService
from aps.services.email import EmailService


def _approve_user(target_user, performed_by, note='', request=None):
    target_user.is_active = True
    target_user.save(update_fields=['is_active'])
    profile, _ = UserProfile.objects.get_or_create(user=target_user)
    profile.approved_at = timezone.now()
    profile.save(update_fields=['approved_at'])
    ApprovalLog.objects.create(
        target_user=target_user, action='approved',
        performed_by=performed_by, note=note,
    )
    AuditService.log_user_action(
        performed_by, AuditLog.ACTION_USER_APPROVED, target_user, note=note, request=request,
    )
    EmailService.send_approval_email(target_user, performed_by=performed_by, request=request)


def _reject_user(target_user, performed_by, note='', request=None):
    target_user.is_active = False
    target_user.save(update_fields=['is_active'])
    ApprovalLog.objects.create(
        target_user=target_user, action='rejected',
        performed_by=performed_by, note=note,
    )
    AuditService.log_user_action(
        performed_by, AuditLog.ACTION_USER_REJECTED, target_user, note=note, request=request,
    )
    EmailService.send_rejection_email(
        target_user, note=note, performed_by=performed_by, request=request,
    )


@admin_required
def approval_requests(request):
    from django.db.models import OuterRef, Subquery, Value
    from django.db.models.functions import Coalesce
    latest_log = ApprovalLog.objects.filter(target_user=OuterRef('pk')).order_by('-created_at')

    base_qs = User.objects.filter(is_superuser=False).annotate(
        latest_action=Coalesce(Subquery(latest_log.values('action')[:1]), Value(''))
    )

    pending_users = base_qs.filter(is_active=False).exclude(latest_action='rejected')
    approved_users = base_qs.filter(is_active=True)
    rejected_users = base_qs.filter(is_active=False, latest_action='rejected')

    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'pending')
    sort = request.GET.get('sort', '-date_joined')

    if status_filter == 'pending':
        qs = pending_users
    elif status_filter == 'approved':
        qs = approved_users
    elif status_filter == 'rejected':
        qs = rejected_users
    else:
        qs = base_qs

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
    qs = qs.order_by(sort_map.get(sort, '-date_joined')).select_related('profile')
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
        'rejected_count': rejected_users.count(),
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

    _approve_user(target_user, request.user, note=note, request=request)

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

    _reject_user(target_user, request.user, note=note, request=request)

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
    from django.db import transaction
    with transaction.atomic():
        for u in users:
            _approve_user(u, request.user, note='Bulk approval', request=request)
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
    from django.db import transaction
    with transaction.atomic():
        for u in users:
            _reject_user(u, request.user, note='Bulk rejection', request=request)
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
