from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User

# Python 3.14 Compatibility Patch for Django Test Client context copying
import django.template.context
def _context_copy(self):
    dup = self.__class__.__new__(self.__class__)
    dup.__dict__.update(self.__dict__)
    dup.dicts = self.dicts[:]
    return dup
django.template.context.BaseContext.__copy__ = _context_copy
from django.contrib.admin.sites import AdminSite
from aps.admin import CustomUserAdmin
from aps.forms import ApprovedUserLoginForm

class UserApprovalTests(TestCase):
    def setUp(self):
        self.register_url = reverse('register')
        self.login_url = reverse('login')
        self.dashboard_url = reverse('dashboard')

    def test_registration_creates_inactive_user(self):
        """Registering a new user should save them as inactive by default."""
        response = self.client.post(self.register_url, {
            'username': 'newuser',
            'full_name': 'New User',
            'email': 'newuser@example.com',
            'country_code': '+91',
            'mobile_number': '9876543210',
            'city': 'Mumbai',
            'password1': 'SecurePassword123!',
            'password2': 'SecurePassword123!',
        })
        # Should redirect to login page upon success
        self.assertRedirects(response, self.login_url)
        
        # Verify user is created but inactive
        user = User.objects.get(username='newuser')
        self.assertFalse(user.is_active)
        self.assertEqual(user.email, 'newuser@example.com')

    def test_registration_allows_duplicate_inactive_username(self):
        """Registering with a username of an existing inactive user should succeed and replace them."""
        # Create an initial inactive user
        initial_user = User.objects.create_user(username='newuser', password='password123', email='old@example.com')
        initial_user.is_active = False
        initial_user.save()

        # Attempt to register again with same username
        response = self.client.post(self.register_url, {
            'username': 'newuser',
            'full_name': 'New User Re-registered',
            'email': 'newuser@example.com',
            'country_code': '+91',
            'mobile_number': '9876543210',
            'city': 'Mumbai',
            'password1': 'SecurePassword123!',
            'password2': 'SecurePassword123!',
        })
        self.assertRedirects(response, self.login_url)

        # Verify new user details replaced the old one
        user = User.objects.get(username='newuser')
        self.assertFalse(user.is_active)
        self.assertEqual(user.email, 'newuser@example.com')
        self.assertEqual(user.first_name, 'New')

    def test_inactive_user_cannot_login(self):
        """An inactive user should get a specific validation error and fail to login."""
        # Create an inactive user
        user = User.objects.create_user(username='inactiveuser', password='password123', email='inactive@example.com')
        user.is_active = False
        user.save()

        # Try to log in
        response = self.client.post(self.login_url, {
            'username': 'inactiveuser',
            'password': 'password123',
        })
        
        # Should render the login page again (not redirect)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'aps/login.html')
        
        # Verify the custom error message is in form errors
        form = response.context['form']
        self.assertIn('__all__', form.errors)
        self.assertIn("Your account is pending admin approval. Please contact the administrator.", form.errors['__all__'])

    def test_active_user_can_login(self):
        """An active user should log in successfully and redirect to the dashboard."""
        user = User.objects.create_user(username='activeuser', password='password123')
        user.is_active = True
        user.save()

        response = self.client.post(self.login_url, {
            'username': 'activeuser',
            'password': 'password123',
        })
        self.assertRedirects(response, self.dashboard_url)

    def test_pending_approval_user_queryset(self):
        """PendingApprovalUser proxy model should only return inactive, non-superuser accounts."""
        from aps.models import PendingApprovalUser
        
        # Create different user categories
        User.objects.create_user(username='inactive_regular', is_active=False)
        User.objects.create_user(username='active_regular', is_active=True)
        User.objects.create_superuser(username='inactive_superuser', password='pw', is_active=False)

        pending_users = PendingApprovalUser.objects.all()
        
        self.assertEqual(pending_users.count(), 1)
        self.assertEqual(pending_users.first().username, 'inactive_regular')

    def test_pending_approvals_count_in_context(self):
        """The context processor should return the correct pending approvals count for admin/staff."""
        # Create an inactive user (should be counted)
        User.objects.create_user(username='pending_user', is_active=False)
        # Create an active user (should not be counted)
        User.objects.create_user(username='active_user', is_active=True)
        # Create an inactive superuser (should not be counted)
        User.objects.create_superuser(username='inactive_super', password='pw', is_active=False)

        from django.test import RequestFactory
        from aps.context_processors import sidebar_context
        from django.contrib.auth.models import AnonymousUser
        
        rf = RequestFactory()
        request = rf.get('/')
        request.user = AnonymousUser()
        self.assertEqual(sidebar_context(request), {})

        # Regular user (should get count = 0)
        regular_user = User.objects.create_user(username='reg', password='pw', is_active=True)
        request.user = regular_user
        context = sidebar_context(request)
        self.assertEqual(context.get('pending_approvals_count'), 0)

        # Staff user (should get count = 1)
        staff_user = User.objects.create_user(username='staff', password='pw', is_active=True, is_staff=True)
        request.user = staff_user
        context = sidebar_context(request)
        self.assertEqual(context.get('pending_approvals_count'), 1)


class WishlistTests(TestCase):
    def setUp(self):
        # Create users
        self.user = User.objects.create_user(username='testuser', password='password123', is_active=True)
        self.client.login(username='testuser', password='password123')
        
        # Create product
        from aps.models import Product, Category
        self.cat = Category.objects.create(name='Electronics')
        self.product1 = Product.objects.create(product_name='Phone', category=self.cat, asin_code='ASIN1', created_by=self.user)
        self.product2 = Product.objects.create(product_name='Laptop', category=self.cat, asin_code='ASIN2', created_by=self.user)

    def test_wishlist_toggle_adds_and_removes(self):
        """Toggling a product should add it to wishlist, and toggling it again should remove it."""
        from aps.models import WishlistItem
        
        # Add to wishlist
        response = self.client.post(reverse('wishlist_toggle', kwargs={'product_id': self.product1.pk}), **{'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['wished'])
        self.assertEqual(data['wishlist_count'], 1)
        self.assertTrue(WishlistItem.objects.filter(user=self.user, product=self.product1).exists())
        
        # Toggle again -> remove from wishlist
        response = self.client.post(reverse('wishlist_toggle', kwargs={'product_id': self.product1.pk}), **{'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['wished'])
        self.assertEqual(data['wishlist_count'], 0)
        self.assertFalse(WishlistItem.objects.filter(user=self.user, product=self.product1).exists())

    def test_wishlist_list_displays_wished_products(self):
        """The wishlist view should only display products currently in the user's wishlist."""
        from aps.models import WishlistItem
        WishlistItem.objects.create(user=self.user, product=self.product1)
        
        response = self.client.get(reverse('wishlist_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'aps/wishlist.html')
        self.assertIn(self.product1, response.context['products'])
        self.assertNotIn(self.product2, response.context['products'])


class CustomUserApprovalUITests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(username='admin_user', password='password123', email='admin@example.com')
        self.regular_user = User.objects.create_user(username='regular_user', password='password123', is_active=True)
        self.pending_user1 = User.objects.create_user(username='pending1', password='password123', is_active=False)
        self.pending_user2 = User.objects.create_user(username='pending2', password='password123', is_active=False)
        
        self.approval_page_url = reverse('approval_requests')
        self.history_api_url = reverse('approval_history_api')

    def test_anonymous_cannot_access_approval_page(self):
        response = self.client.get(self.approval_page_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_regular_user_cannot_access_approval_page(self):
        self.client.login(username='regular_user', password='password123')
        response = self.client.get(self.approval_page_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_admin_can_access_approval_page(self):
        self.client.login(username='admin_user', password='password123')
        response = self.client.get(self.approval_page_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'aps/approval_requests.html')
        self.assertIn(self.pending_user1, response.context['users'])

    def test_approve_user_api(self):
        self.client.login(username='admin_user', password='password123')
        url = reverse('approve_user_api', kwargs={'user_id': self.pending_user1.pk})
        
        response = self.client.post(url, {'note': 'Approved for access'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        self.pending_user1.refresh_from_db()
        self.assertTrue(self.pending_user1.is_active)
        
        # Check audit log
        from aps.models import ApprovalLog
        log = ApprovalLog.objects.filter(target_user=self.pending_user1).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.action, 'approved')
        self.assertEqual(log.performed_by, self.admin_user)
        self.assertEqual(log.note, 'Approved for access')

    def test_approve_user_api_with_permissions(self):
        self.client.login(username='admin_user', password='password123')
        url = reverse('approve_user_api', kwargs={'user_id': self.pending_user1.pk})
        
        response = self.client.post(url, {
            'note': 'Approved with custom permissions',
            'can_export': 'true',
            'can_manage_all_orders': 'true',
            'can_manage_settings': 'false',
            'can_delete_products': 'true',
            'can_delete_inventory': 'false',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        self.pending_user1.refresh_from_db()
        self.assertTrue(self.pending_user1.is_active)
        
        profile = self.pending_user1.profile
        self.assertTrue(profile.can_export)
        self.assertTrue(profile.can_manage_all_orders)
        self.assertFalse(profile.can_manage_settings)
        self.assertTrue(profile.can_delete_products)
        self.assertFalse(profile.can_delete_inventory)

    def test_reject_user_api(self):
        self.client.login(username='admin_user', password='password123')
        url = reverse('reject_user_api', kwargs={'user_id': self.pending_user1.pk})
        
        response = self.client.post(url, {'note': 'Rejected - no business need'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        self.pending_user1.refresh_from_db()
        self.assertFalse(self.pending_user1.is_active)
        
        # Check audit log
        from aps.models import ApprovalLog
        log = ApprovalLog.objects.filter(target_user=self.pending_user1).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.action, 'rejected')
        self.assertEqual(log.performed_by, self.admin_user)
        self.assertEqual(log.note, 'Rejected - no business need')

    def test_bulk_approve_api(self):
        self.client.login(username='admin_user', password='password123')
        url = reverse('bulk_approve_api')
        
        import json
        response = self.client.post(url, json.dumps({'user_ids': [self.pending_user1.pk, self.pending_user2.pk]}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        self.pending_user1.refresh_from_db()
        self.pending_user2.refresh_from_db()
        self.assertTrue(self.pending_user1.is_active)
        self.assertTrue(self.pending_user2.is_active)

    def test_bulk_reject_api(self):
        self.client.login(username='admin_user', password='password123')
        url = reverse('bulk_reject_api')
        
        import json
        response = self.client.post(url, json.dumps({'user_ids': [self.pending_user1.pk, self.pending_user2.pk]}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        self.pending_user1.refresh_from_db()
        self.pending_user2.refresh_from_db()
        self.assertFalse(self.pending_user1.is_active)
        self.assertFalse(self.pending_user2.is_active)


class RBACOrderTests(TestCase):
    def setUp(self):
        from datetime import date
        from aps.models import Category, Product, Order

        self.user1 = User.objects.create_user('orderuser1', password='password123', is_active=True)
        self.user2 = User.objects.create_user('orderuser2', password='password123', is_active=True)
        self.admin = User.objects.create_superuser('orderadmin', password='password123')

        cat = Category.objects.create(name='TestCat')
        self.product = Product.objects.create(
            product_name='Test Product', category=cat, asin_code='RBAC1',
        )
        self.order = Order.objects.create(
            product=self.product, quantity=2, price=100,
            order_date=date.today(), created_by=self.user1,
        )

    def test_user_cannot_access_other_users_order(self):
        self.client.login(username='orderuser2', password='password123')
        url = reverse('order_detail_api', kwargs={'pk': self.order.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_user_can_access_own_order(self):
        self.client.login(username='orderuser1', password='password123')
        url = reverse('order_detail_api', kwargs={'pk': self.order.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], self.order.pk)

    def test_admin_can_access_any_order(self):
        self.client.login(username='orderadmin', password='password123')
        url = reverse('order_detail_api', kwargs={'pk': self.order.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_order_list_scoped_to_user(self):
        from aps.permissions import filter_orders_for_user
        scoped = filter_orders_for_user(self.user2)
        self.assertEqual(scoped.count(), 0)
        self.assertEqual(filter_orders_for_user(self.user1).count(), 1)


class RBACSettingsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('settingsuser', password='password123', is_active=True)
        self.admin = User.objects.create_superuser('settingsadmin', password='password123')
        
        # Complete settings setup wizard so user can be blocked
        from aps.models import ProductCodeSettings
        ProductCodeSettings.objects.create(user=self.user, enabled=True)
        
        # Disable setting management on their profile
        profile = self.user.profile
        profile.can_manage_settings = False
        profile.save()

    def test_regular_user_cannot_access_settings(self):
        self.client.login(username='settingsuser', password='password123')
        response = self.client.get(reverse('settings'))
        self.assertEqual(response.status_code, 302)

    def test_admin_can_access_settings(self):
        self.client.login(username='settingsadmin', password='password123')
        response = self.client.get(reverse('settings'))
        self.assertEqual(response.status_code, 200)


class AuditLogTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('auditadmin', password='password123')
        self.pending = User.objects.create_user('auditpending', password='password123', is_active=False)

    def test_approve_creates_audit_log(self):
        from aps.models import AuditLog
        self.client.login(username='auditadmin', password='password123')
        url = reverse('approve_user_api', kwargs={'user_id': self.pending.pk})
        response = self.client.post(url, {'note': 'Welcome'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.ACTION_USER_APPROVED,
                object_id=self.pending.pk,
            ).exists()
        )


class AdminControlTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ctrluser', password='password123', is_active=True)
        self.admin = User.objects.create_superuser('ctrladmin', password='password123')

    def test_regular_user_cannot_access_admin_control(self):
        self.client.login(username='ctrluser', password='password123')
        response = self.client.get(reverse('admin_control'))
        self.assertEqual(response.status_code, 302)

    def test_admin_can_access_admin_control(self):
        self.client.login(username='ctrladmin', password='password123')
        response = self.client.get(reverse('admin_control'))
        self.assertEqual(response.status_code, 200)


class OrderCalculationTests(TestCase):
    def setUp(self):
        from aps.models import Category, Product
        self.cat = Category.objects.create(name='TestCat')
        self.product = Product.objects.create(
            product_name='Test Product', category=self.cat, asin_code='RBAC1',
        )

    def test_calculation_by_carton(self):
        """If carton_piece is 0, total_amount should be quantity * rupees."""
        from datetime import date
        from aps.models import Order
        order = Order.objects.create(
            product=self.product, quantity=5, rmb=10, exchange_value=85,
            carton_piece=0, order_date=date.today()
        )
        # rupees = 10 * 85 = 850
        # total_amount = 5 * 850 = 4250
        self.assertEqual(order.rupees, 850)
        self.assertEqual(order.total_amount, 4250)
        self.assertEqual(order.total_pieces, 0)

    def test_calculation_by_pieces(self):
        """If carton_piece > 0, total_amount should be quantity * carton_piece * rupees."""
        from datetime import date
        from aps.models import Order
        order = Order.objects.create(
            product=self.product, quantity=5, rmb=10, exchange_value=85,
            carton_piece=12, order_date=date.today()
        )
        # rupees = 10 * 85 = 850
        # total_pieces = 5 * 12 = 60
        # total_amount = 60 * 850 = 51000
        self.assertEqual(order.rupees, 850)
        self.assertEqual(order.total_pieces, 60)
        self.assertEqual(order.total_amount, 51000)


class OrderSortingTests(TestCase):
    def setUp(self):
        from datetime import date, timedelta
        from aps.models import Category, Product, Order
        self.user = User.objects.create_user('sortinguser', password='password123', is_active=True)
        self.cat = Category.objects.create(name='TestCat')
        self.product = Product.objects.create(
            product_name='Test Product', category=self.cat, asin_code='SORT1',
        )
        # Order 1: Price 1000, Date Today
        self.o1 = Order.objects.create(
            product=self.product, quantity=1, price=1000, rupees=1000,
            total_amount=1000, order_date=date.today(), created_by=self.user
        )
        # Order 2: Price 5000, Date Yesterday
        self.o2 = Order.objects.create(
            product=self.product, quantity=1, price=5000, rupees=5000,
            total_amount=5000, order_date=date.today() - timedelta(days=1), created_by=self.user
        )

    def test_sorting_by_price_low_to_high(self):
        from unittest.mock import patch
        from django.test import RequestFactory
        from aps.views.orders import order_list
        rf = RequestFactory()
        request = rf.get('/orders/?sort=total_amount')
        request.user = self.user
        with patch('aps.views.orders.render') as mock_render:
            order_list(request)
            context = mock_render.call_args[0][2]
            orders = list(context['page_obj'].object_list)
            # Low to High: o1 (1000), o2 (5000)
            self.assertEqual(orders[0], self.o1)
            self.assertEqual(orders[1], self.o2)

    def test_sorting_by_price_high_to_low(self):
        from unittest.mock import patch
        from django.test import RequestFactory
        from aps.views.orders import order_list
        rf = RequestFactory()
        request = rf.get('/orders/?sort=-total_amount')
        request.user = self.user
        with patch('aps.views.orders.render') as mock_render:
            order_list(request)
            context = mock_render.call_args[0][2]
            orders = list(context['page_obj'].object_list)
            # High to Low: o2 (5000), o1 (1000)
            self.assertEqual(orders[0], self.o2)
            self.assertEqual(orders[1], self.o1)


class ProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='profileuser', password='password123', is_active=True, first_name='John', last_name='Doe', email='john@example.com')
        profile = self.user.profile
        profile.mobile_number = '9876543210'
        profile.country_code = '+91'
        profile.city = 'Mumbai'
        profile.save()
        self.profile_url = reverse('profile')

    def test_anonymous_cannot_access_profile(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 302)

    def test_authenticated_user_can_view_profile(self):
        self.client.login(username='profileuser', password='password123')
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'aps/profile.html')
        self.assertEqual(response.context['profile'].city, 'Mumbai')
        self.assertEqual(response.context['profile'].mobile_number, '9876543210')

    def test_authenticated_user_can_edit_profile(self):
        self.client.login(username='profileuser', password='password123')
        # Edit request
        response = self.client.post(self.profile_url, {
            'update_profile': '1',
            'full_name': 'Johnny Doe',
            'email': 'johnny@example.com',
            'country_code': '+91',
            'mobile_number': '9876543211',
            'city': 'Delhi',
        })
        self.assertRedirects(response, self.profile_url)
        
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Johnny')
        self.assertEqual(self.user.last_name, 'Doe')
        self.assertEqual(self.user.email, 'johnny@example.com')
        self.assertEqual(self.user.profile.mobile_number, '9876543211')
        self.assertEqual(self.user.profile.city, 'Delhi')

    def test_forgot_password_generates_otp(self):
        from aps.models import PasswordResetOTP
        url = reverse('forgot_password')
        response = self.client.post(url, {
            'identifier': 'john@example.com',
        })
        # Should redirect to verify_otp
        self.assertRedirects(response, reverse('verify_otp'))
        
        # Verify OTP was created
        otp_record = PasswordResetOTP.objects.filter(user=self.user).first()
        self.assertIsNotNone(otp_record)
        self.assertFalse(otp_record.is_used)

    def test_verify_otp_and_reset_password(self):
        from aps.models import PasswordResetOTP
        from django.utils import timezone
        import datetime
        
        # Create OTP manually
        otp = '123456'
        PasswordResetOTP.objects.create(
            user=self.user, otp=otp, expires_at=timezone.now() + datetime.timedelta(minutes=10)
        )
        
        # Simulate session from forgot_password
        session = self.client.session
        session['reset_user_id'] = self.user.id
        session.save()
        
        # Verify OTP
        response = self.client.post(reverse('verify_otp'), {'otp': otp})
        self.assertRedirects(response, reverse('reset_password'))
        
        # Reset Password
        response = self.client.post(reverse('reset_password'), {
            'password': 'NewSecurePassword123!',
            'confirm_password': 'NewSecurePassword123!',
        })
        self.assertRedirects(response, reverse('login'))
        
        # Verify user can log in with new password
        self.assertTrue(self.client.login(username='profileuser', password='NewSecurePassword123!'))

    def test_otp_rate_limiting(self):
        from aps.models import PasswordResetOTP
        from django.utils import timezone
        import datetime
        
        # Create 3 OTPs
        for _ in range(3):
            PasswordResetOTP.objects.create(
                user=self.user, otp='000000', expires_at=timezone.now() + datetime.timedelta(minutes=10)
            )
            
        url = reverse('forgot_password')
        response = self.client.post(url, {
            'identifier': 'john@example.com',
        })
        self.assertRedirects(response, reverse('verify_otp'))
        
        # Count should still be 3, new one not created
        self.assertEqual(PasswordResetOTP.objects.filter(user=self.user).count(), 3)


class CategoriesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('catuser', password='password123', is_active=True)
        self.admin = User.objects.create_superuser('catadmin', password='password123')
        self.categories_url = reverse('categories_list')

        # Complete setup wizard for both catuser and catadmin
        from aps.models import Category, SubCategory, ProductCodeSettings
        ProductCodeSettings.objects.create(user=self.user, enabled=True)
        c = Category.objects.create(name='DummyCat', created_by=self.user)
        SubCategory.objects.create(category=c, name='DummySub')

        ProductCodeSettings.objects.create(user=self.admin, enabled=True)
        c2 = Category.objects.create(name='AdminDummyCat', created_by=self.admin)
        SubCategory.objects.create(category=c2, name='AdminDummySub')

    def test_anonymous_cannot_access_categories(self):
        response = self.client.get(self.categories_url)
        self.assertEqual(response.status_code, 302)

    def test_regular_user_can_access_categories(self):
        self.client.login(username='catuser', password='password123')
        response = self.client.get(self.categories_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'aps/categories.html')

    def test_admin_redirected_from_categories(self):
        self.client.login(username='catadmin', password='password123')
        response = self.client.get(self.categories_url)
        # Administrators are redirected from business pages to user list
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('users_list'), response.url)

    def test_add_category_and_subcategory(self):
        from aps.models import Category, SubCategory
        self.client.login(username='catuser', password='password123')
        
        # Add category
        response = self.client.post(self.categories_url, {
            'form_type': 'category',
            'name': 'New Category'
        })
        self.assertRedirects(response, self.categories_url)
        cat = Category.objects.filter(name='New Category', created_by=self.user).first()
        self.assertIsNotNone(cat)

        # Add subcategory
        response = self.client.post(self.categories_url, {
            'form_type': 'subcategory',
            'category': cat.id,
            'name': 'New Subcategory'
        })
        self.assertRedirects(response, self.categories_url)
        self.assertTrue(SubCategory.objects.filter(name='New Subcategory', category=cat).exists())

    def test_edit_category(self):
        from aps.models import Category
        self.client.login(username='catuser', password='password123')
        cat = Category.objects.filter(created_by=self.user).first()
        
        response = self.client.post(reverse('category_edit_api'), {
            'category_id': cat.id,
            'name': 'Updated Category Name'
        })
        self.assertRedirects(response, self.categories_url)
        cat.refresh_from_db()
        self.assertEqual(cat.name, 'Updated Category Name')

    def test_edit_subcategory(self):
        from aps.models import SubCategory
        self.client.login(username='catuser', password='password123')
        sub = SubCategory.objects.filter(category__created_by=self.user).first()
        
        response = self.client.post(reverse('subcategory_edit_api'), {
            'subcategory_id': sub.id,
            'category': sub.category.id,
            'name': 'Updated Subcat Name'
        })
        self.assertRedirects(response, self.categories_url)
        sub.refresh_from_db()
        self.assertEqual(sub.name, 'Updated Subcat Name')


class AsinCodeCollisionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('produser', password='password123', is_active=True)

    def test_asin_collision_resolution(self):
        from aps.models import Product
        import datetime
        now = datetime.datetime.now()
        year = now.year
        month = now.strftime('%m')
        day = now.strftime('%d')

        expected_code_1 = f"{year}{month}{day}0001"
        expected_code_2 = f"{year}{month}{day}0002"

        # Create a product with a hardcoded code matching the first generated sequence code
        Product.objects.create(
            product_name='Pre-existing Product',
            asin_code=expected_code_1,
            created_by=self.user
        )

        # Now, try to create another product where code is auto-generated
        p2 = Product.objects.create(
            product_name='New Product',
            created_by=self.user
        )

        # Verify that it resolved the collision by incrementing sequence to expected_code_2
        self.assertEqual(p2.asin_code, expected_code_2)


class ProductCodeFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testformuser', password='password123', is_active=True)
        from aps.models import Category
        self.category = Category.objects.create(name='Electronics', created_by=self.user)

    def test_product_form_does_not_contain_asin_code(self):
        from aps.forms import ProductForm
        form = ProductForm(user=self.user)
        self.assertNotIn('asin_code', form.fields)

    def test_product_auto_generation_format_and_sequence(self):
        from aps.models import Product
        import datetime
        now = datetime.datetime.now()
        year = now.year
        month = now.strftime('%m')
        day = now.strftime('%d')

        # Create first product
        p1 = Product.objects.create(
            product_name='Product One',
            category=self.category,
            created_by=self.user
        )
        expected_code_1 = f"{year}{month}{day}0001"
        self.assertEqual(p1.asin_code, expected_code_1)

        # Create second product (sequence increments)
        p2 = Product.objects.create(
            product_name='Product Two',
            category=self.category,
            created_by=self.user
        )
        expected_code_2 = f"{year}{month}{day}0002"
        self.assertEqual(p2.asin_code, expected_code_2)

    def test_product_sequence_persists_across_logins(self):
        from aps.models import Product, ProductCodeSequence
        import datetime
        now = datetime.datetime.now()
        year = now.year
        month = now.strftime('%m')
        day = now.strftime('%d')

        # Create a product
        p1 = Product.objects.create(
            product_name='Product One',
            category=self.category,
            created_by=self.user
        )
        self.assertEqual(p1.asin_code, f"{year}{month}{day}0001")

        # Simulate relogin (logging in again or retrieving sequence from DB)
        # Verify that the sequence continues
        seq = ProductCodeSequence.objects.get(user=self.user, year=0, month='ALL')
        self.assertEqual(seq.last_sequence, 1)

        p2 = Product.objects.create(
            product_name='Product Two',
            category=self.category,
            created_by=self.user
        )
        self.assertEqual(p2.asin_code, f"{year}{month}{day}0002")

    def test_product_auto_generation_with_ref_date(self):
        from aps.models import Product
        import datetime
        
        # Test generation with a fixed reference date (e.g. 5 days ago)
        ref_date = datetime.datetime.now() - datetime.timedelta(days=5)
        year = ref_date.year
        month = ref_date.strftime('%m')
        day = ref_date.strftime('%d')

        code = Product._generate_asin_code(user=self.user, ref_date=ref_date)
        self.assertEqual(code, f"{year}{month}{day}0001")




