from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
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

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = user

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise ValidationError('Category name cannot be blank.')
        # Check uniqueness per user
        if self._user and Category.objects.filter(name=name, created_by=self._user).exists():
            raise ValidationError('You already have a category with this name.')
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

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].empty_label = '— Select Category —'
        if user:
            self.fields['category'].queryset = Category.objects.filter(created_by=user)

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise ValidationError('Subcategory name cannot be blank.')
        return name

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        name = cleaned_data.get('name', '').strip()
        if category and name:
            if SubCategory.objects.filter(category=category, name=name).exists():
                raise ValidationError(f'Subcategory "{name}" already exists in this category.')
        return cleaned_data


# ── Product (Catalogue) Form ─────────────────────────────────────────────────

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['product_name', 'sh_code', 'category', 'subcategory', 'main_image', 'description', 'tags']
        labels = {
            'sh_code': 'Product Code',
        }
        widgets = {
            'product_name': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Product name',
                'autocomplete': 'off',
            }),
            'sh_code': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Product Code (optional)',
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

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = user
        self.fields['category'].empty_label = '— Select Category —'
        self.fields['subcategory'].empty_label = '— Select Subcategory —'
        self.fields['subcategory'].queryset = SubCategory.objects.none()

        # Scope categories to user
        if user:
            self.fields['category'].queryset = Category.objects.filter(created_by=user)

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
        labels = {
            'location_number': 'Shop Number',
            'price': 'RMB',
            'cbm': '1 Carton CBM',
        }
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
            'quantity', 'rmb', 'exchange_value', 'rupees', 'price', 'deposit',
            'cbm', 'carton_piece', 'location_number', 'remark', 'order_date',
        ]
        labels = {
            'location_number': 'Shop',
            'cbm': '1 Carton CBM',
            'price': 'Rupees',
        }
        widgets = {
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': '1',
                'min': '1',
                'id': 'id_quantity',
            }),
            'rmb': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
                'id': 'id_rmb',
            }),
            'exchange_value': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
                'id': 'id_exchange_value',
            }),
            'rupees': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
                'id': 'id_rupees',
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


# ── User Registration & Login Forms ──────────────────────────────────────────

COUNTRY_CODE_CHOICES = [
    ('+91', 'India (+91)'),
    ('+1', 'USA (+1)'),
    ('+44', 'UK (+44)'),
    ('+971', 'UAE (+971)'),
    ('+86', 'China (+86)'),
    ('+65', 'Singapore (+65)'),
]


class UserRegistrationForm(UserCreationForm):
    full_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter full name',
            'autocomplete': 'name',
        }),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter email address',
            'autocomplete': 'email',
        }),
    )
    country_code = forms.ChoiceField(
        choices=COUNTRY_CODE_CHOICES,
        initial='+91',
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
    )
    mobile_number = forms.CharField(
        max_length=15,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': '10-digit mobile number',
            'autocomplete': 'tel',
            'inputmode': 'numeric',
        }),
    )
    city = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter city',
            'autocomplete': 'address-level2',
        }),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ('username', 'password1', 'password2', 'full_name', 'email',
                           'mobile_number', 'city'):
            if field_name in self.fields:
                field = self.fields[field_name]
                if not isinstance(field.widget, forms.Select):
                    field.widget.attrs.setdefault('class', 'form-control form-control-lg')

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if not email:
            raise ValidationError('Email is required.')
        if User.objects.filter(email=email).exists():
            raise ValidationError('A user with this email address already exists.')
        return email

    def clean_mobile_number(self):
        from .models import UserProfile
        from .validators import validate_mobile_number
        country_code = self.cleaned_data.get('country_code', '+91')
        mobile = validate_mobile_number(
            self.cleaned_data.get('mobile_number', ''), country_code=country_code,
        )
        if UserProfile.objects.filter(mobile_number=mobile).exists():
            raise ValidationError('This mobile number is already registered.')
        return mobile

    def save(self, commit=True):
        user = super().save(commit=False)
        full_name = self.cleaned_data.get('full_name', '').strip()
        parts = full_name.split(None, 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ''
        if commit:
            user.save()
            from .models import UserProfile
            UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    'mobile_number': self.cleaned_data['mobile_number'],
                    'country_code': self.cleaned_data['country_code'],
                    'city': self.cleaned_data['city'],
                },
            )
        return user


class ApprovedUserLoginForm(AuthenticationForm):
    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            try:
                user = User.objects.get(username=username)
                if not user.is_active:
                    raise ValidationError(
                        "Your account is pending admin approval. Please contact the administrator.",
                        code='pending_approval',
                    )
            except User.DoesNotExist:
                # Let parent handle non-existent user or wrong password authentication
                pass

        return super().clean()


class UserProfileEditForm(forms.ModelForm):
    full_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter full name',
            'autocomplete': 'name',
        }),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter email address',
            'autocomplete': 'email',
        }),
    )
    country_code = forms.ChoiceField(
        choices=COUNTRY_CODE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
    )
    mobile_number = forms.CharField(
        max_length=15,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Mobile number',
            'autocomplete': 'tel',
            'inputmode': 'numeric',
        }),
    )
    city = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter city',
            'autocomplete': 'address-level2',
        }),
    )

    class Meta:
        model = User
        fields = ('email',)

    def __init__(self, *args, user=None, **kwargs):
        self._user = user
        # Initialize form with current values
        initial = kwargs.get('initial', {})
        if user:
            initial['email'] = user.email
            initial['full_name'] = f"{user.first_name} {user.last_name}".strip()
            profile = getattr(user, 'profile', None)
            if profile:
                initial['country_code'] = profile.country_code
                initial['mobile_number'] = profile.mobile_number
                initial['city'] = profile.city
        kwargs['initial'] = initial
        super().__init__(*args, **kwargs)
        for field_name in ('full_name', 'email', 'mobile_number', 'city'):
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.setdefault('class', 'form-control form-control-lg')

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if not email:
            raise ValidationError('Email is required.')
        if User.objects.filter(email=email).exclude(pk=self._user.pk).exists():
            raise ValidationError('A user with this email address already exists.')
        return email

    def clean_mobile_number(self):
        from .models import UserProfile
        from .validators import validate_mobile_number
        country_code = self.cleaned_data.get('country_code', '+91')
        mobile = validate_mobile_number(
            self.cleaned_data.get('mobile_number', ''), country_code=country_code,
        )
        if UserProfile.objects.filter(mobile_number=mobile).exclude(user=self._user).exists():
            raise ValidationError('This mobile number is already registered.')
        return mobile

    def save(self, commit=True):
        user = self._user
        user.email = self.cleaned_data.get('email', '').strip()
        full_name = self.cleaned_data.get('full_name', '').strip()
        parts = full_name.split(None, 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ''
        if commit:
            user.save()
            from .models import UserProfile
            UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    'mobile_number': self.cleaned_data['mobile_number'],
                    'country_code': self.cleaned_data['country_code'],
                    'city': self.cleaned_data['city'],
                },
            )
        return user