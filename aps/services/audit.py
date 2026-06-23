"""
Immutable audit logging service for all critical business events.
"""
import json

from aps.models import AuditLog


def _get_client_ip(request):
    if not request:
        return None
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _get_user_agent(request):
    if not request:
        return ''
    return (request.META.get('HTTP_USER_AGENT') or '')[:500]


class AuditService:
    """Centralized, append-only audit logging."""

    @staticmethod
    def log(user, action, *, object_type='', object_id=None, object_repr='',
            details=None, request=None):
        details_text = ''
        if details is not None:
            if isinstance(details, (dict, list)):
                details_text = json.dumps(details, default=str)
            else:
                details_text = str(details)

        return AuditLog.objects.create(
            user=user if user and user.is_authenticated else None,
            action=action,
            object_type=object_type,
            object_id=object_id,
            object_repr=object_repr[:255] if object_repr else '',
            details=details_text,
            ip_address=_get_client_ip(request),
            user_agent=_get_user_agent(request),
        )

    @classmethod
    def log_login(cls, user, request=None):
        return cls.log(user, AuditLog.ACTION_LOGIN, object_type='user',
                       object_id=user.pk, object_repr=user.username, request=request)

    @classmethod
    def log_logout(cls, user, request=None):
        return cls.log(user, AuditLog.ACTION_LOGOUT, object_type='user',
                       object_id=user.pk if user else None,
                       object_repr=user.username if user else '', request=request)

    @classmethod
    def log_product(cls, user, action, product, details=None, request=None):
        return cls.log(
            user, action,
            object_type='product',
            object_id=product.pk,
            object_repr=product.product_name,
            details=details,
            request=request,
        )

    @classmethod
    def log_inventory(cls, user, action, inventory, details=None, request=None):
        return cls.log(
            user, action,
            object_type='inventory',
            object_id=inventory.pk,
            object_repr=str(inventory),
            details=details,
            request=request,
        )

    @classmethod
    def log_order(cls, user, action, order, details=None, request=None):
        return cls.log(
            user, action,
            object_type='order',
            object_id=order.pk,
            object_repr=str(order),
            details=details,
            request=request,
        )

    @classmethod
    def log_export(cls, user, export_type, record_count=0, request=None):
        return cls.log(
            user, AuditLog.ACTION_EXPORT,
            object_type=export_type,
            object_repr=f'{export_type} export',
            details={'record_count': record_count},
            request=request,
        )

    @classmethod
    def log_user_action(cls, user, action, target_user, note='', request=None, details=None):
        log_details = {'note': note}
        if details:
            log_details.update(details)
        return cls.log(
            user, action,
            object_type='user',
            object_id=target_user.pk,
            object_repr=target_user.username,
            details=log_details,
            request=request,
        )
