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
            from django.db import transaction
            try:
                with transaction.atomic():
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
            except Exception as e:
                messages.error(request, 'An error occurred during registration. Please try again.')
                return render(request, 'aps/register.html', {'page_title': 'Register Access', 'form': form})

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
    """Generate OTP and send it to the user's email address without revealing account existence."""
        
    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        if not identifier:
            messages.error(request, 'Please enter your username or email address.')
            return render(request, 'aps/forgot_password.html')
            
        from django.contrib.auth.models import User
        from django.db.models import Q
        
        user = User.objects.filter(Q(username=identifier) | Q(email=identifier)).first()
        
        # Security: Always show the same success message to prevent enumeration
        success_msg = 'If an account exists with that identifier, an OTP has been sent to the associated email.'
        
        if user and user.email:
            from aps.models import PasswordResetOTP
            from django.utils import timezone
            import datetime
            # Check rate limit (e.g. no more than 3 active OTPs)
            recent_otps = PasswordResetOTP.objects.filter(
                user=user, 
                created_at__gte=timezone.now() - datetime.timedelta(minutes=10)
            ).count()
            
            if recent_otps >= 3:
                # Silently fail or log, but still show success to user
                pass
            else:
                import secrets
                otp = ''.join(secrets.choice('0123456789') for i in range(6))
                expires_at = timezone.now() + datetime.timedelta(minutes=10)
                otp_record = PasswordResetOTP.objects.create(
                    user=user, otp=otp, expires_at=expires_at
                )
                
                # Send Email
                from django.core.mail import send_mail
                from django.conf import settings
                from django.template.loader import render_to_string
                
                subject = 'Your WMS Account Password Reset OTP'
                context = {'username': user.username, 'otp': otp, 'expiry_minutes': 10}
                # Fallback to text if template missing
                try:
                    html_message = render_to_string('emails/otp_email.html', context)
                    text_message = render_to_string('emails/otp_email.txt', context)
                except Exception:
                    html_message = None
                    text_message = f"Hello {user.username},\n\nYour OTP is: {otp}\nIt expires in 10 minutes.\n"
                
                try:
                    if html_message:
                        from django.core.mail import EmailMultiAlternatives
                        msg = EmailMultiAlternatives(subject, text_message, settings.DEFAULT_FROM_EMAIL or 'noreply@wms.local', [user.email])
                        msg.attach_alternative(html_message, "text/html")
                        msg.send(fail_silently=False)
                    else:
                        send_mail(subject, text_message, settings.DEFAULT_FROM_EMAIL or 'noreply@wms.local', [user.email], fail_silently=False)
                        
                    request.session['reset_user_id'] = user.id
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to send password reset email: {e}")
                    if settings.DEBUG:
                        print(f"\n[LOCAL DEV] OTP for {user.username}: {otp}\n")
                        request.session['reset_user_id'] = user.id
                        messages.success(request, f'[LOCAL DEV] Simulated OTP sent. Check console. {success_msg}')
                        return redirect('verify_otp')
                    else:
                        otp_record.delete()
                        messages.error(request, 'An error occurred while sending the email. Please try again later.')
                        return render(request, 'aps/forgot_password.html')
                        
                messages.success(request, success_msg)
                return redirect('verify_otp')
                
        # If user not found, still redirect and show success message
        messages.success(request, success_msg)
        return redirect('verify_otp')
            
    return render(request, 'aps/forgot_password.html')

def verify_otp_view(request):
    user_id = request.session.get('reset_user_id')
    
    if request.method == 'POST':
        otp_entered = request.POST.get('otp', '').strip()
        if not otp_entered:
            messages.error(request, 'Please enter the OTP.')
            return render(request, 'aps/verify_otp.html')
            
        if user_id:
            from aps.models import PasswordResetOTP
            from django.contrib.auth.models import User
            user = User.objects.filter(id=user_id).first()
            if user:
                otp_record = PasswordResetOTP.objects.filter(
                    user=user, otp=otp_entered, is_used=False
                ).order_by('-created_at').first()
                
                if otp_record:
                    if otp_record.is_expired:
                        messages.error(request, 'OTP has expired. Please request a new one.')
                        return redirect('forgot_password')
                        
                    # OTP is valid
                    otp_record.is_used = True
                    otp_record.save(update_fields=['is_used'])
                    
                    import uuid
                    reset_token = str(uuid.uuid4())
                    request.session['reset_token'] = reset_token
                    
                    from aps.services.audit import AuditService
                    from aps.models import AuditLog
                    AuditService.log(user, AuditLog.ACTION_SETTINGS_CHANGED, details={'note': 'OTP verified successfully'}, request=request)
                    
                    messages.success(request, 'OTP verified successfully. You can now reset your password.')
                    return redirect('reset_password')
                    
        messages.error(request, 'Invalid OTP. Please try again.')
        
    return render(request, 'aps/verify_otp.html')

def reset_password_view(request):
    user_id = request.session.get('reset_user_id')
    reset_token = request.session.get('reset_token')
    
    if not user_id or not reset_token:
        messages.error(request, 'Session expired or invalid request. Please start over.')
        return redirect('forgot_password')
        
    if request.method == 'POST':
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        if not password or not confirm_password:
            messages.error(request, 'Please fill out both fields.')
            return render(request, 'aps/reset_password.html')
            
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'aps/reset_password.html')
            
        from django.contrib.auth.models import User
        user = User.objects.filter(id=user_id).first()
        if user:
            user.set_password(password)
            user.save()
            from aps.services.audit import AuditService
            from aps.models import AuditLog
            AuditService.log(user, AuditLog.ACTION_SETTINGS_CHANGED, details={'note': 'Password reset via OTP'}, request=request)
            
            # Clear session
            request.session.pop('reset_user_id', None)
            request.session.pop('reset_token', None)
            
            messages.success(request, 'Your password has been reset successfully. You can now log in.')
            return redirect('login')
        else:
            messages.error(request, 'Invalid user.')
            return redirect('forgot_password')
            
    return render(request, 'aps/reset_password.html')
