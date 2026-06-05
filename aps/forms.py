from django import forms
from django.core.exceptions import ValidationError
from .models import (
    Category, SubCategory, Product,
    WarehouseInventory, CartonImage, InventoryProductImage, InventoryVideo,
    ProductCodeSettings,
)

MAX_CARTON_IMAGES = 2
MAX_PRODUCT_IMAGES = 5


# ── Classification Forms ─────────────────────────────────────────────────────

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Category name',
                'autocomplete': 'off',
            })
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise ValidationError('Category name cannot be blank.')
        return name


class SubCategoryForm(forms.ModelForm):
    class Meta:
        model = SubCategory
        fields = ['category', 'name']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select form-select-lg'}),
            'name': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Subcategory name',
                'autocomplete': 'off',
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].empty_label = '— Select Category —'

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise ValidationError('Subcategory name cannot be blank.')
        return name


# ── Product (Catalogue) Form ─────────────────────────────────────────────────

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['product_name', 'sh_code', 'category', 'subcategory', 'main_image', 'description', 'tags']
        widgets = {
            'product_name': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Product name',
                'autocomplete': 'off',
            }),
            'sh_code': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'SH Code (optional)',
            }),
            'category': forms.Select(attrs={
                'class': 'form-select form-select-lg',
                'id': 'id_category',
            }),
            'subcategory': forms.Select(attrs={
                'class': 'form-select form-select-lg',
                'id': 'id_subcategory',
            }),
            'main_image': forms.ClearableFileInput(attrs={
                'class': 'form-control form-control-lg',
                'accept': 'image/*',
                'capture': 'environment',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Product description',
                'rows': 3,
            }),
            'tags': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Comma-separated tags (e.g. plastic, metal, tools)',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].empty_label = '— Select Category —'
        self.fields['subcategory'].empty_label = '— Select Subcategory —'
        self.fields['subcategory'].queryset = SubCategory.objects.none()

        if 'category' in self.data:
            try:
                cat_id = int(self.data.get('category'))
                self.fields['subcategory'].queryset = SubCategory.objects.filter(
                    category_id=cat_id
                )
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.category:
            self.fields['subcategory'].queryset = SubCategory.objects.filter(
                category=self.instance.category
            )


# ── Warehouse Inventory Form ─────────────────────────────────────────────────

class WarehouseInventoryForm(forms.ModelForm):
    class Meta:
        model = WarehouseInventory
        fields = ['location_number', 'price', 'carton_piece', 'cbm', 'remark']
        widgets = {
            'location_number': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'e.g. A1, B2, C3',
                'autocomplete': 'off',
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
            }),
            'carton_piece': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': '0',
                'min': '0',
            }),
            'cbm': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': '0.0000',
                'step': '0.0001',
                'min': '0',
            }),
            'remark': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional notes...',
            }),
        }


# ── Product Code Settings Form ───────────────────────────────────────────────

class ProductCodeSettingsForm(forms.ModelForm):
    class Meta:
        model = ProductCodeSettings
        fields = ['enabled', 'prefix_format', 'sequence_length', 'reset_monthly']
        widgets = {
            'enabled': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_code_enabled',
            }),
            'prefix_format': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': '{YEAR}{MONTH}{SEQ}',
                'id': 'id_prefix_format',
            }),
            'sequence_length': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'min': '1', 'max': '10',
                'id': 'id_seq_length',
            }),
            'reset_monthly': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_reset_monthly',
            }),
        }


# ── Order Form ───────────────────────────────────────────────────────────────

from .models import Order

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = [
            'quantity', 'price', 'deposit', 'cbm', 'carton_piece',
            'location_number', 'remark', 'order_date',
        ]
        widgets = {
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': '1',
                'min': '1',
                'id': 'id_quantity',
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
                'id': 'id_price',
            }),
            'deposit': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
                'id': 'id_deposit',
            }),
            'cbm': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': '0.0000',
                'step': '0.0001',
                'min': '0',
                'id': 'id_cbm',
            }),
            'carton_piece': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': '0',
                'min': '0',
                'id': 'id_carton_piece',
            }),
            'location_number': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'e.g. A1, B2, C3',
                'autocomplete': 'off',
                'id': 'id_location_number',
            }),
            'remark': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Additional notes...',
                'id': 'id_remark',
            }),
            'order_date': forms.DateInput(attrs={
                'class': 'form-control form-control-lg',
                'type': 'date',
                'id': 'id_order_date',
            }),
        }