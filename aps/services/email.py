"""
SMTP email delivery for user approval and rejection notifications.
"""
import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.db import connection

from aps.models import AuditLog

logger = logging.getLogger(__name__)


def _send_email_async(msg, to_email, performed_by, subject, html_template, request_ip, request_ua):
    """Worker function to send email asynchronously and log the outcome."""
    from aps.services.audit import AuditService
    try:
        msg.send(fail_silently=False)
        AuditLog.objects.create(
            user=performed_by if performed_by and performed_by.is_authenticated else None,
            action=AuditLog.ACTION_EMAIL_SENT,
            object_type='email',
            object_repr=to_email[:255] if to_email else '',
            details=f'{{"subject": "{subject}", "template": "{html_template}"}}',
            ip_address=request_ip,
            user_agent=request_ua,
        )
    except Exception as exc:
        logger.exception('Email send failed to %s', to_email)
        try:
            AuditLog.objects.create(
                user=performed_by if performed_by and performed_by.is_authenticated else None,
                action=AuditLog.ACTION_EMAIL_FAILED,
                object_type='email',
                object_repr=to_email[:255] if to_email else '',
                details=f'{{"subject": "{subject}", "error": "{str(exc)}"}}',
                ip_address=request_ip,
                user_agent=request_ua,
            )
        except Exception as inner_exc:
            logger.exception('Failed to log email failure to audit: %s', inner_exc)
    finally:
        # Close the connection for the thread to prevent leakages
        connection.close()


class EmailService:
    """Reusable SMTP email service."""

    @staticmethod
    def _send(subject, to_email, html_template, text_template, context, *,
              performed_by=None, target_user=None, request=None):
        if not to_email:
            return False, 'No recipient email address.'

        try:
            html_body = render_to_string(html_template, context)
            text_body = render_to_string(text_template, context)
            from_email = settings.DEFAULT_FROM_EMAIL

            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_body,
                from_email=from_email,
                to=[to_email],
            )
            msg.attach_alternative(html_body, 'text/html')

            # Pre-extract request meta info for the background logging
            from aps.services.audit import _get_client_ip, _get_user_agent
            request_ip = _get_client_ip(request) if request else None
            request_ua = _get_user_agent(request) if request else ''

            # If in testing, run synchronously to avoid SQLite database locks and support assertions
            if getattr(settings, 'IS_TESTING', False):
                _send_email_async(msg, to_email, performed_by, subject, html_template, request_ip, request_ua)
            else:
                thread = threading.Thread(
                    target=_send_email_async,
                    args=(msg, to_email, performed_by, subject, html_template, request_ip, request_ua),
                    daemon=True
                )
                thread.start()
            return True, None
        except Exception as exc:
            logger.exception('Email rendering or thread startup failed to %s', to_email)
            return False, str(exc)

    @classmethod
    def send_approval_email(cls, user, performed_by=None, request=None):
        context = {
            'username': user.username,
            'email': user.email,
            'login_url': request.build_absolute_uri('/login/') if request else '/login/',
        }
        return cls._send(
            subject='Your WMS account has been approved',
            to_email=user.email,
            html_template='emails/approval_email.html',
            text_template='emails/approval_email.txt',
            context=context,
            performed_by=performed_by,
            target_user=user,
            request=request,
        )

    @classmethod
    def send_rejection_email(cls, user, note='', performed_by=None, request=None):
        context = {
            'username': user.username,
            'email': user.email,
            'note': note,
        }
        return cls._send(
            subject='Your WMS registration request',
            to_email=user.email,
            html_template='emails/rejection_email.html',
            text_template='emails/rejection_email.txt',
            context=context,
            performed_by=performed_by,
            target_user=user,
            request=request,
        )

    @classmethod
    def send_otp_email(cls, user, otp, request=None):
        context = {
            'username': user.username,
            'otp': otp,
            'expiry_minutes': 10,
        }
        return cls._send(
            subject='Your WMS Account Password Reset OTP',
            to_email=user.email,
            html_template='emails/otp_email.html',
            text_template='emails/otp_email.txt',
            context=context,
            performed_by=user,
            target_user=user,
            request=request,
        )
