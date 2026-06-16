from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from aps.permissions import is_administrator
from aps.services.dashboard import DashboardService


@login_required
def dashboard(request):
    if is_administrator(request.user):
        stats = DashboardService.company_stats(request.user)
        context = {
            'page_title': 'Admin Dashboard',
            'active_menu': 'dashboard',
            'is_admin_dashboard': True,
            **stats,
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
