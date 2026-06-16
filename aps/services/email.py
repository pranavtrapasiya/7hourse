"""
SMTP email delivery for user approval and rejection notifications.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from aps.models import AuditLog
from aps.services.audit import AuditService

logger = logging.getLogger(__name__)


class EmailService:
    """Reusable SMTP email service."""

    @staticmethod
    def _send(subject, to_email, html_template, text_template, context, *,
              performed_by=None, target_user=None, request=None):
        if not to_email:
            return False, 'No recipient email address.'

        html_body = render_to_string(html_template, context)
        text_body = render_to_string(text_template, context)
        from_email = settings.DEFAULT_FROM_EMAIL

        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_body,
                from_email=from_email,
                to=[to_email],
            )
            msg.attach_alternative(html_body, 'text/html')
            msg.send(fail_silently=False)
            AuditService.log(
                performed_by,
                AuditLog.ACTION_EMAIL_SENT,
                object_type='email',
                object_repr=to_email,
                details={'subject': subject, 'template': html_template},
                request=request,
            )
            return True, None
        except Exception as exc:
            logger.exception('Email send failed to %s', to_email)
            AuditService.log(
                performed_by,
                AuditLog.ACTION_EMAIL_FAILED,
                object_type='email',
                object_repr=to_email,
                details={'subject': subject, 'error': str(exc)},
                request=request,
            )
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
