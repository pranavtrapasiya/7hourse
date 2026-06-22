"""
Auth signals for audit logging on login.
"""
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User

from aps.models import (
    UserProfile, CartonImage, InventoryProductImage, InventoryVideo, Product
)
from aps.services.audit import AuditService


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    AuditService.log_login(user, request=request)


@receiver(post_delete, sender=CartonImage)
@receiver(post_delete, sender=InventoryProductImage)
def delete_image_file_on_delete(sender, instance, **kwargs):
    if getattr(instance, 'image', None):
        instance.image.delete(save=False)


@receiver(post_delete, sender=InventoryVideo)
def delete_video_file_on_delete(sender, instance, **kwargs):
    if getattr(instance, 'video', None):
        instance.video.delete(save=False)


@receiver(post_delete, sender=Product)
def delete_product_image_on_delete(sender, instance, **kwargs):
    if getattr(instance, 'main_image', None):
        instance.main_image.delete(save=False)
