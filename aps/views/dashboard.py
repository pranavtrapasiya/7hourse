from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from aps.permissions import is_administrator
from aps.services.dashboard import DashboardService


@login_required
def dashboard(request):
    if is_administrator(request.user):
        stats = DashboardService.company_stats()
        user_stats = DashboardService.user_stats(request.user)
        context = {
            'page_title': 'Dashboard',
            'active_menu': 'dashboard',
            'is_admin_dashboard': True,
            **stats,
            'my_orders': user_stats['my_orders'],
            'my_orders_this_week': user_stats['my_orders_this_week'],
            'pending_payment_orders': user_stats['pending_payment_orders'],
            'recent_orders': user_stats['recent_orders'],
        }
    else:
        stats = DashboardService.user_stats(request.user)
        context = {
            'page_title': 'My Dashboard',
            'active_menu': 'dashboard',
            'is_admin_dashboard': False,
            **stats,
            'total_orders': stats['my_orders'],
        }
    return render(request, 'aps/dashboard.html', context)
