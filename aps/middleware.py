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
