from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect

from aps.forms import UserRegistrationForm
from aps.services.audit import AuditService


def register_view(request):
    """Allow registration of new company staff, pending admin approval."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()
            from aps.models import UserProfile
            UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    'mobile_number': form.cleaned_data['mobile_number'],
                    'country_code': form.cleaned_data['country_code'],
                    'city': form.cleaned_data['city'],
                },
            )
            messages.success(
                request,
                'Your account registration request has been submitted. '
                'It is pending approval by the administrator.',
            )
            return redirect('login')
        messages.error(request, 'Please correct the errors in the registration form.')
    else:
        form = UserRegistrationForm()

    return render(request, 'aps/register.html', {
        'page_title': 'Register Access',
        'form': form,
    })


@login_required
def logout_view(request):
    user = request.user
    AuditService.log_logout(user, request=request)
    from django.contrib.auth import logout as django_logout
    django_logout(request)
    return redirect('login')
