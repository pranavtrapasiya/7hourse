import uuid
import datetime
from django.db import models, transaction
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
    name = models.CharField(max_length=150, unique=True)

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['name']

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

# ── Product Code Settings (Singleton) ────────────────────────────────────────

class ProductCodeSettings(models.Model):
    """Singleton settings for auto product code generation."""
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
        return 'Product Code Settings'

    def save(self, *args, **kwargs):
        self.pk = 1  # singleton
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ProductCodeSequence(models.Model):
    """Tracks auto-increment sequence counters per year/month."""
    year = models.PositiveIntegerField()
    month = models.CharField(max_length=3)  # JAN, FEB, ...
    last_sequence = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('year', 'month')
        verbose_name = 'Product Code Sequence'

    def __str__(self):
        return f'{self.year} {self.month} — seq {self.last_sequence}'


# ── Master Product (Catalogue) ───────────────────────────────────────────────

class Product(models.Model):
    """
    Master product record — catalogue data only.
    No warehouse/price/location data here.
    Supports soft-delete for data protection.
    """
    product_name = models.CharField(max_length=255, db_index=True)
    asin_code = models.CharField(max_length=100, unique=True, blank=True, null=True, db_index=True)
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

    # ── Soft Delete ──
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product_name', 'is_deleted'], name='idx_product_name_active'),
            models.Index(fields=['category', 'is_deleted'], name='idx_product_cat_active'),
            models.Index(fields=['is_deleted', '-created_at'], name='idx_product_active_date'),
        ]

    def __str__(self):
        return self.product_name

    def save(self, *args, **kwargs):
        if not self.asin_code:
            self.asin_code = self._generate_asin_code()
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
    def _generate_asin_code():
        """
        Generate the next product code using ProductCodeSettings.
        Uses select_for_update() for atomic, collision-proof generation.
        Thread-safe and concurrency-safe.
        """
        settings = ProductCodeSettings.load()
        if not settings.enabled:
            return None

        now = datetime.datetime.now()
        year = now.year
        month = now.strftime('%b').upper()  # JAN, FEB, ...

        with transaction.atomic():
            if settings.reset_monthly:
                seq_obj, created = ProductCodeSequence.objects.select_for_update().get_or_create(
                    year=year, month=month, defaults={'last_sequence': 0}
                )
            else:
                seq_obj, created = ProductCodeSequence.objects.select_for_update().get_or_create(
                    year=year, month='ALL', defaults={'last_sequence': 0}
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


# Add the active manager to Product without replacing default
Product.add_to_class('active_objects', ActiveProductManager())


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
        'auth.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='orders'
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
        # Auto-calculate derived fields
        self.total_cbm = self.quantity * self.cbm                          # Carton Qty × CBM
        self.total_pieces = self.price * self.carton_piece                 # Price × Pcs in One Carton
        self.total_amount = self.quantity * self.total_pieces              # Carton Qty × Total Pieces (Payment)
        self.remaining_to_pay = self.total_amount - self.deposit           # Payment − Deposit
        super().save(*args, **kwargs)