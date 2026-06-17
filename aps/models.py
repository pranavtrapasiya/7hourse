import uuid
import datetime
from django.db import models, transaction
from django.contrib.auth.models import User
from django.db.models import F
from .validators import (
    validate_image_extension,
    validate_image_size,
    validate_video_extension,
    validate_video_size,
)


# ── Upload path helpers ──────────────────────────────────────────────────────

def product_main_image_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    return f'products/{uuid.uuid4().hex}/main/{uuid.uuid4().hex}.{ext}'


def carton_image_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    return f'inventory/{instance.inventory.pk}/carton/{uuid.uuid4().hex}.{ext}'


def inv_product_image_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    return f'inventory/{instance.inventory.pk}/product_images/{uuid.uuid4().hex}.{ext}'


def inv_video_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    return f'inventory/{instance.inventory.pk}/video/{uuid.uuid4().hex}.{ext}'


# ── Core Classification Models ───────────────────────────────────────────────

class Category(models.Model):
    name = models.CharField(max_length=150)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='categories_created',
    )

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['name']
        unique_together = ('name', 'created_by')

    def __str__(self):
        return self.name


class SubCategory(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='subcategories'
    )
    name = models.CharField(max_length=150)

    class Meta:
        verbose_name = 'Sub Category'
        verbose_name_plural = 'Sub Categories'
        ordering = ['name']
        unique_together = ('category', 'name')

    def __str__(self):
        return f'{self.category.name} > {self.name}'

# ── Product Code Settings (Per-User) ─────────────────────────────────────────

class ProductCodeSettings(models.Model):
    """Per-user settings for auto product code generation."""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='product_code_settings',
        null=True, blank=True,
    )
    enabled = models.BooleanField(default=True, verbose_name='Enable Auto Product Code')
    prefix_format = models.CharField(
        max_length=100, default='{YEAR}{MONTH}{SEQ}',
        help_text='Template: {YEAR}, {MONTH}, {SEQ}'
    )
    sequence_length = models.PositiveIntegerField(default=4)
    reset_monthly = models.BooleanField(default=True, verbose_name='Reset Sequence Monthly')

    class Meta:
        verbose_name = 'Product Code Settings'
        verbose_name_plural = 'Product Code Settings'

    def __str__(self):
        username = self.user.username if self.user else 'Global'
        return f'Product Code Settings ({username})'

    @classmethod
    def load(cls, user=None):
        """Load or create settings for a specific user."""
        obj, _ = cls.objects.get_or_create(user=user)
        return obj


class ProductCodeSequence(models.Model):
    """Tracks auto-increment sequence counters per user/year/month."""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='product_code_sequences',
    )
    year = models.PositiveIntegerField()
    month = models.CharField(max_length=3)  # JAN, FEB, ...
    last_sequence = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('user', 'year', 'month')
        verbose_name = 'Product Code Sequence'

    def __str__(self):
        username = self.user.username if self.user else 'Global'
        return f'{username} — {self.year} {self.month} — seq {self.last_sequence}'


# ── Master Product (Catalogue) ───────────────────────────────────────────────

class Product(models.Model):
    """
    Master product record — catalogue data only.
    No warehouse/price/location data here.
    Supports soft-delete for data protection.
    """
    product_name = models.CharField(max_length=255, db_index=True)
    asin_code = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    sh_code = models.CharField(max_length=100, blank=True, db_index=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='products'
    )
    subcategory = models.ForeignKey(
        SubCategory,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='products'
    )
    main_image = models.ImageField(
        upload_to=product_main_image_path,
        validators=[validate_image_extension, validate_image_size],
        blank=True, null=True
    )
    description = models.TextField(blank=True)
    tags = models.CharField(max_length=255, blank=True, help_text="Comma-separated tags")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='products_created',
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='products_updated',
    )
    updated_at = models.DateTimeField(auto_now=True)

    # ── Soft Delete ──
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('asin_code', 'created_by')
        indexes = [
            models.Index(fields=['product_name', 'is_deleted'], name='idx_product_name_active'),
            models.Index(fields=['category', 'is_deleted'], name='idx_product_cat_active'),
            models.Index(fields=['is_deleted', '-created_at'], name='idx_product_active_date'),
        ]

    def __str__(self):
        return self.product_name

    def save(self, *args, **kwargs):
        if not self.asin_code and self.created_by:
            self.asin_code = self._generate_asin_code(self.created_by)
        super().save(*args, **kwargs)

    def soft_delete(self):
        """Mark product as deleted without removing from database."""
        from django.utils import timezone
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])

    def restore(self):
        """Restore a soft-deleted product."""
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at'])

    @staticmethod
    def _generate_asin_code(user=None):
        """
        Generate the next product code using per-user ProductCodeSettings.
        Uses select_for_update() for atomic, collision-proof generation.
        Thread-safe and concurrency-safe.
        """
        settings = ProductCodeSettings.load(user=user)
        if not settings.enabled:
            return None

        now = datetime.datetime.now()
        year = now.year
        month = now.strftime('%b').upper()  # JAN, FEB, ...

        with transaction.atomic():
            if settings.reset_monthly:
                seq_obj, created = ProductCodeSequence.objects.select_for_update().get_or_create(
                    user=user, year=year, month=month, defaults={'last_sequence': 0}
                )
            else:
                seq_obj, created = ProductCodeSequence.objects.select_for_update().get_or_create(
                    user=user, year=year, month='ALL', defaults={'last_sequence': 0}
                )

            seq_obj.last_sequence = F('last_sequence') + 1
            seq_obj.save(update_fields=['last_sequence'])
            seq_obj.refresh_from_db()
            next_seq = seq_obj.last_sequence

        seq_str = str(next_seq).zfill(settings.sequence_length)
        code = settings.prefix_format.replace('{YEAR}', str(year))
        code = code.replace('{MONTH}', month)
        code = code.replace('{SEQ}', seq_str)
        return code

    @property
    def primary_image(self):
        return self.main_image if self.main_image else None

    @property
    def latest_inventory(self):
        return self.inventory_entries.order_by('-created_at').first()


# ── Active Products Manager ─────────────────────────────────────────────────

class ActiveProductManager(models.Manager):
    """Manager that only returns non-deleted products."""
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


# ── Ownership-Aware Managers ────────────────────────────────────────────────

class OwnershipQuerySet(models.QuerySet):
    """Base queryset with ownership filtering capabilities."""
    def for_user(self, user):
        """Filter records owned by the user, or all records for administrators."""
        from aps.permissions import is_administrator
        if is_administrator(user):
            return self
        return self.filter(created_by=user)


class OwnershipManager(models.Manager):
    """Manager that provides ownership-aware querysets."""
    def get_queryset(self):
        return OwnershipQuerySet(self.model, using=self._db)

    def for_user(self, user):
        """Return records owned by the user, or all records for administrators."""
        return self.get_queryset().for_user(user)


# Add the active manager to Product without replacing default
Product.add_to_class('active_objects', ActiveProductManager())
Product.add_to_class('owned_objects', OwnershipManager())


# ── Warehouse Inventory Entry ────────────────────────────────────────────────

class WarehouseInventory(models.Model):
    """
    A warehouse entry for a product: location, pricing, qty, media.
    A product can have multiple inventory entries over time.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='inventory_entries'
    )
    location_number = models.CharField(max_length=50, blank=True, db_index=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    carton_piece = models.PositiveIntegerField(default=0)
    cbm = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    remark = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='inventory_created',
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='inventory_updated',
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Warehouse Inventory'
        verbose_name_plural = 'Warehouse Inventory Entries'

    def __str__(self):
        return f'{self.product.product_name} @ {self.location_number or "—"}'

    @property
    def carton_image_count(self):
        return self.carton_images.count()

    @property
    def product_image_count(self):
        return self.product_images.count()


# Add ownership manager to WarehouseInventory
WarehouseInventory.add_to_class('owned_objects', OwnershipManager())


class CartonImage(models.Model):
    """Up to 2 carton images per inventory entry."""
    inventory = models.ForeignKey(
        WarehouseInventory,
        on_delete=models.CASCADE,
        related_name='carton_images'
    )
    image = models.ImageField(
        upload_to=carton_image_path,
        validators=[validate_image_extension, validate_image_size]
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='carton_images_uploaded',
    )

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        return f'Carton image for {self.inventory}'


class InventoryProductImage(models.Model):
    """Up to 5 product images per inventory entry."""
    inventory = models.ForeignKey(
        WarehouseInventory,
        on_delete=models.CASCADE,
        related_name='product_images'
    )
    image = models.ImageField(
        upload_to=inv_product_image_path,
        validators=[validate_image_extension, validate_image_size]
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='product_images_uploaded',
    )

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        return f'Product image for {self.inventory}'


class InventoryVideo(models.Model):
    """One video per inventory entry."""
    inventory = models.OneToOneField(
        WarehouseInventory,
        on_delete=models.CASCADE,
        related_name='video'
    )
    video = models.FileField(
        upload_to=inv_video_path,
        validators=[validate_video_extension, validate_video_size]
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='videos_uploaded',
    )

    def __str__(self):
        return f'Video for {self.inventory}'


# ── Order ────────────────────────────────────────────────────────────────────

class Order(models.Model):
    """
    Order entry linking a Product and an optional WarehouseInventory (location).
    Stores pricing, quantity, and auto-calculated summaries.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='orders'
    )
    location = models.ForeignKey(
        WarehouseInventory,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='orders'
    )

    # ── Core fields ──
    quantity = models.PositiveIntegerField(default=1)
    rmb = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='RMB')
    exchange_value = models.DecimalField(
        max_digits=12, decimal_places=4, default=1, verbose_name='Value',
    )
    rupees = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='Rupees')
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deposit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cbm = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    carton_piece = models.PositiveIntegerField(default=0)
    location_number = models.CharField(max_length=50, blank=True)
    remark = models.TextField(blank=True)

    # ── Calculated fields (stored for reporting) ──
    remaining_to_pay = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cbm = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    total_pieces = models.PositiveIntegerField(default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # ── Metadata ──
    order_date = models.DateField()
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='orders'
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='orders_updated',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'

    def __str__(self):
        return f'Order #{self.pk} — {self.product.product_name}'

    def save(self, *args, **kwargs):
        from decimal import Decimal
        rmb = Decimal(str(self.rmb or 0))
        value = Decimal(str(self.exchange_value or 1))
        if rmb > 0 and value > 0:
            self.rupees = rmb * value
        elif not self.rupees and self.price:
            self.rupees = self.price
        self.price = self.rupees
        self.total_cbm = self.quantity * self.cbm
        self.total_pieces = self.quantity * (self.carton_piece or 0)
        
        if self.carton_piece and self.carton_piece > 0:
            self.total_amount = Decimal(str(self.total_pieces)) * self.rupees
        else:
            self.total_amount = Decimal(str(self.quantity)) * self.rupees
            
        self.remaining_to_pay = self.total_amount - self.deposit
        super().save(*args, **kwargs)


# Add ownership manager to Order
Order.add_to_class('owned_objects', OwnershipManager())


# ── Proxy Model for Pending Approvals ─────────────────────────────────────────

class PendingApprovalUserManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=False, is_superuser=False)


class PendingApprovalUser(User):
    objects = PendingApprovalUserManager()

    class Meta:
        proxy = True
        verbose_name = 'Pending Approval'
        verbose_name_plural = 'Pending Approvals'


# ── Approval Audit Log ───────────────────────────────────────────────────────

class ApprovalLog(models.Model):
    """
    Immutable audit log for user approval/rejection actions.
    Records cannot be edited or deleted from the application.
    """
    ACTION_CHOICES = [
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    target_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='approval_logs',
        help_text='The user being approved or rejected',
    )
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='approval_actions_performed',
        help_text='The admin who performed the action',
    )
    note = models.TextField(blank=True, help_text='Optional reason for the action')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Approval Log'
        verbose_name_plural = 'Approval Logs'

    def __str__(self):
        return f'{self.get_action_display()} — {self.target_user.username} by {self.performed_by}'


# ── Wishlist Model ───────────────────────────────────────────────────────────

class WishlistItem(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='wishlist_items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='wished_by'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('user', 'product')
        verbose_name = 'Wishlist Item'
        verbose_name_plural = 'Wishlist Items'

    def __str__(self):
        return f'{self.user.username} wished {self.product.product_name}'


# ── User Profile & Granular Permissions ─────────────────────────────────────

class UserProfile(models.Model):
    """
    Extended profile for company staff with optional permission grants.
    Administrators (is_staff/is_superuser) have unrestricted access regardless.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    can_export = models.BooleanField(
        default=False,
        help_text='Allow exporting company-wide data.',
    )
    can_manage_all_orders = models.BooleanField(
        default=False,
        help_text='View and manage orders created by other users.',
    )
    can_manage_settings = models.BooleanField(
        default=False,
        help_text='Access system settings and product code configuration.',
    )
    can_delete_products = models.BooleanField(
        default=False,
        help_text='Soft-delete, restore, and permanently delete products.',
    )
    can_delete_inventory = models.BooleanField(
        default=False,
        help_text='Delete warehouse inventory entries.',
    )
    mobile_number = models.CharField(max_length=15, blank=True, db_index=True)
    country_code = models.CharField(max_length=5, default='+91')
    city = models.CharField(max_length=100, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f'Profile: {self.user.username}'


# ── Immutable Audit Log ───────────────────────────────────────────────────────

class AuditLog(models.Model):
    """
    Immutable audit trail for all critical business events.
    Records cannot be edited or deleted from the application UI.
    """
    ACTION_LOGIN = 'login'
    ACTION_LOGOUT = 'logout'
    ACTION_USER_APPROVED = 'user_approved'
    ACTION_USER_REJECTED = 'user_rejected'
    ACTION_USER_DEACTIVATED = 'user_deactivated'
    ACTION_USER_ACTIVATED = 'user_activated'
    ACTION_PRODUCT_CREATED = 'product_created'
    ACTION_PRODUCT_UPDATED = 'product_updated'
    ACTION_PRODUCT_DELETED = 'product_deleted'
    ACTION_PRODUCT_RESTORED = 'product_restored'
    ACTION_PRODUCT_PERMANENT_DELETE = 'product_permanent_delete'
    ACTION_INVENTORY_CREATED = 'inventory_created'
    ACTION_INVENTORY_UPDATED = 'inventory_updated'
    ACTION_INVENTORY_DELETED = 'inventory_deleted'
    ACTION_LOCATION_CHANGED = 'location_changed'
    ACTION_ORDER_CREATED = 'order_created'
    ACTION_ORDER_UPDATED = 'order_updated'
    ACTION_ORDER_DELETED = 'order_deleted'
    ACTION_EXPORT = 'export'
    ACTION_SETTINGS_CHANGED = 'settings_changed'
    ACTION_CATEGORY_CREATED = 'category_created'
    ACTION_SUBCATEGORY_CREATED = 'subcategory_created'
    ACTION_WISHLIST_ADD = 'wishlist_add'
    ACTION_WISHLIST_REMOVE = 'wishlist_remove'
    ACTION_PERMISSION_CHANGED = 'permission_changed'
    ACTION_EMAIL_SENT = 'email_sent'
    ACTION_EMAIL_FAILED = 'email_failed'

    ACTION_CHOICES = [
        (ACTION_LOGIN, 'Login'),
        (ACTION_LOGOUT, 'Logout'),
        (ACTION_USER_APPROVED, 'User Approved'),
        (ACTION_USER_REJECTED, 'User Rejected'),
        (ACTION_USER_DEACTIVATED, 'User Deactivated'),
        (ACTION_USER_ACTIVATED, 'User Activated'),
        (ACTION_PRODUCT_CREATED, 'Product Created'),
        (ACTION_PRODUCT_UPDATED, 'Product Updated'),
        (ACTION_PRODUCT_DELETED, 'Product Deleted'),
        (ACTION_PRODUCT_RESTORED, 'Product Restored'),
        (ACTION_PRODUCT_PERMANENT_DELETE, 'Product Permanently Deleted'),
        (ACTION_INVENTORY_CREATED, 'Inventory Created'),
        (ACTION_INVENTORY_UPDATED, 'Inventory Updated'),
        (ACTION_INVENTORY_DELETED, 'Inventory Deleted'),
        (ACTION_LOCATION_CHANGED, 'Location Changed'),
        (ACTION_ORDER_CREATED, 'Order Created'),
        (ACTION_ORDER_UPDATED, 'Order Updated'),
        (ACTION_ORDER_DELETED, 'Order Deleted'),
        (ACTION_EXPORT, 'Data Export'),
        (ACTION_SETTINGS_CHANGED, 'Settings Changed'),
        (ACTION_CATEGORY_CREATED, 'Category Created'),
        (ACTION_SUBCATEGORY_CREATED, 'Subcategory Created'),
        (ACTION_WISHLIST_ADD, 'Wishlist Add'),
        (ACTION_WISHLIST_REMOVE, 'Wishlist Remove'),
        (ACTION_PERMISSION_CHANGED, 'Permission Changed'),
        (ACTION_EMAIL_SENT, 'Email Sent'),
        (ACTION_EMAIL_FAILED, 'Email Failed'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs',
        help_text='User who performed the action.',
    )
    action = models.CharField(max_length=40, choices=ACTION_CHOICES, db_index=True)
    object_type = models.CharField(max_length=50, blank=True, db_index=True)
    object_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    object_repr = models.CharField(max_length=255, blank=True)
    details = models.TextField(blank=True, help_text='JSON or text details of the change.')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        indexes = [
            models.Index(fields=['action', '-created_at'], name='idx_audit_action_date'),
            models.Index(fields=['user', '-created_at'], name='idx_audit_user_date'),
            models.Index(fields=['object_type', 'object_id'], name='idx_audit_object'),
        ]

    def __str__(self):
        who = self.user.username if self.user else 'System'
        return f'{self.get_action_display()} by {who} at {self.created_at}'


# ── Password Reset OTP ───────────────────────────────────────────────────────

class PasswordResetOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_otps')
    otp = models.CharField(max_length=6)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"OTP for {self.user.username}"
        
    @property
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at