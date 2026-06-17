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


@login_required
def profile_view(request):
    """View and update logged-in user's profile details & change password."""
    from aps.forms import UserProfileEditForm
    from aps.models import UserProfile, AuditLog
    from django.contrib.auth.forms import PasswordChangeForm
    from django.contrib.auth import update_session_auth_hash
    
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    # Initialize forms
    profile_form = UserProfileEditForm(user=request.user)
    password_form = PasswordChangeForm(request.user)
    
    active_tab = 'view-profile'
    
    if request.method == 'POST':
        if 'update_profile' in request.POST:
            active_tab = 'edit-profile'
            profile_form = UserProfileEditForm(request.POST, user=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Your profile has been updated successfully.')
                return redirect('profile')
            messages.error(request, 'Please correct the errors below.')
            
        elif 'change_password' in request.POST:
            active_tab = 'change-password'
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)  # Keep user logged in
                messages.success(request, 'Your password has been changed successfully.')
                return redirect('profile')
            messages.error(request, 'Please correct the errors below.')
        
    product_count = request.user.products_created.filter(is_deleted=False).count()
    inventory_count = request.user.inventory_created.count()
    order_count = request.user.orders.count()
    
    last_login_log = AuditLog.objects.filter(
        user=request.user, action=AuditLog.ACTION_LOGIN
    ).order_by('-created_at').first()
    
    context = {
        'page_title': 'My Profile',
        'active_menu': 'profile',
        'profile': profile,
        'form': profile_form,
        'password_form': password_form,
        'product_count': product_count,
        'inventory_count': inventory_count,
        'order_count': order_count,
        'last_login': last_login_log.created_at if last_login_log else request.user.last_login,
        'active_tab': active_tab,
    }
    return render(request, 'aps/profile.html', context)


def forgot_password_view(request):
    """Generate a temporary password and send it to the user's email address."""
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        if not identifier:
            messages.error(request, 'Please enter your username or email address.')
            return render(request, 'aps/forgot_password.html')
            
        from django.contrib.auth.models import User
        from django.db.models import Q
        
        user = User.objects.filter(Q(username=identifier) | Q(email=identifier)).first()
        if user:
            if not user.email:
                messages.error(request, 'Your account does not have an associated email address. Please contact an administrator.')
                return render(request, 'aps/forgot_password.html')
                
            # Generate temporary password
            temp_pass = User.objects.make_random_password(length=10)
            user.set_password(temp_pass)
            user.save()
            
            # Send Email
            from django.core.mail import send_mail
            from django.conf import settings
            
            subject = 'Your WMS Account Temporary Password'
            message = (
                f"Hello {user.username},\n\n"
                f"A password reset was requested for your Warehouse Management System (WMS) account.\n"
                f"Your new temporary password is:\n\n"
                f"    {temp_pass}\n\n"
                f"Please log in and change your password immediately in your profile settings.\n\n"
                f"Best regards,\n"
                f"WMS Admin Team"
            )
            
            email_sent = False
            try:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL or 'noreply@wms.local',
                    [user.email],
                    fail_silently=False,
                )
                email_sent = True
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send password reset email: {e}")
            
            if settings.DEBUG:
                # Print to terminal for local development ease
                print(f"\n[LOCAL DEV] Password Reset for {user.username}: {temp_pass}\n")
                try:
                    with open(settings.BASE_DIR / 'temp_password.txt', 'w') as f:
                        f.write(temp_pass)
                except Exception:
                    pass
            
            if email_sent:
                messages.success(request, f'A temporary password has been successfully sent to {user.email}.')
            else:
                # Fallback message for local development if SMTP fails
                messages.success(
                    request, 
                    f'Temporary password generated: "{temp_pass}" (Email sending failed. Simulated output sent to terminal console for local debugging).'
                )
            return redirect('login')
        else:
            messages.error(request, 'No account found with that username or email address.')
            
    return render(request, 'aps/forgot_password.html')
