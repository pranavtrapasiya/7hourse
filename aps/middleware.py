"""
Middleware to enforce active-user access and block deactivated accounts mid-session.
"""
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.contrib import messages


class ActiveUserMiddleware:
    """Force logout for inactive or unapproved users."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.user.is_active:
            logout(request)
            messages.warning(
                request,
                'Your account is inactive or pending approval. Please contact an administrator.',
            )
            return redirect('login')
        return self.get_response(request)


class SetupWizardMiddleware:
    """Enforce return to setup wizard after saving on setup pages."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        if request.user.is_authenticated and not (request.user.is_staff or request.user.is_superuser) and response.status_code == 302:
            from django.urls import reverse
            try:
                cat_url = reverse('categories_list')
                set_url = reverse('settings')
            except Exception:
                cat_url = '/categories/'
                set_url = '/settings/'

            if request.path in [cat_url, set_url]:
                from aps.models import Category, SubCategory, ProductCodeSettings
                has_category = Category.objects.filter(created_by=request.user).exists()
                has_subcategory = SubCategory.objects.filter(category__created_by=request.user).exists()
                has_settings = ProductCodeSettings.objects.filter(user=request.user).exists()
                
                if not (has_category and has_subcategory and has_settings):
                    try:
                        response['Location'] = reverse('dashboard')
                    except Exception:
                        response['Location'] = '/'
        return response
