import os
import django
from decimal import Decimal
from django.contrib.auth.models import User
from django.utils import timezone
from aps.models import Category, SubCategory, Product, WarehouseInventory, Order, ApprovalLog, ProductCodeSettings
from aps.permissions import filter_products_own, filter_inventory_own, filter_orders_own

def create_categories(user, count):
    cats = []
    prefix = user.username
    for i in range(1, count + 1):
        cat = Category.objects.create(name=f"{prefix} Category {i}", created_by=user)
        sub = SubCategory.objects.create(category=cat, name=f"{prefix} Subcategory {i}.1")
        cats.append((cat, sub))
    return cats

def seed_and_test():
    print("Starting Seeding Process...")
    admin = User.objects.get(username='admin')
    
    # 1. Admin Categories
    print("Creating Admin Categories...")
    admin_cats = create_categories(admin, 5)
    
    # 2. Create Test Users
    print("Creating Users...")
    users = []
    for i in range(1, 6):
        u = User.objects.create_user(username=f'user{i}', email=f'user{i}@example.com', password='Password123!')
        u.is_active = False
        u.save()
        users.append(u)
        # init settings
        ProductCodeSettings.load(user=u)
    
    user1, user2, user3, user4, user5 = users
    
    # Approve user1, user2
    for u in [user1, user2]:
        u.is_active = True
        u.save()
        ApprovalLog.objects.create(target_user=u, action='approved', performed_by=admin, note='Approved for testing')
    
    # Reject user3, user4, user5
    for u in [user3, user4, user5]:
        ApprovalLog.objects.create(target_user=u, action='rejected', performed_by=admin, note='Rejected for testing')
        
    print(f"Users created. Approved: {[u.username for u in User.objects.filter(is_active=True, is_superuser=False)]}")
    print(f"Rejected: {[u.username for u in User.objects.filter(is_active=False)]}")

    # 3. User Settings Data
    print("Creating User Categories...")
    user1_cats = create_categories(user1, 5)
    user2_cats = create_categories(user2, 5)
    
    # Verify Category Isolation
    admin_cat_count = Category.objects.filter(created_by=admin).count()
    user1_cat_count = Category.objects.filter(created_by=user1).count()
    user2_cat_count = Category.objects.filter(created_by=user2).count()
    print(f"Category Isolation Check: Admin ({admin_cat_count}), User1 ({user1_cat_count}), User2 ({user2_cat_count})")
    assert admin_cat_count == 5
    assert user1_cat_count == 5
    assert user2_cat_count == 5
    
    # 4 & 5 & 6. Create Products, Locations, Orders
    def create_plo(user, cats_subs):
        for idx, (cat, sub) in enumerate(cats_subs):
            # Product
            prod = Product(
                product_name=f"{user.username} Product {idx+1}",
                sh_code=f"SH-{user.username}-{idx+1}",
                category=cat,
                subcategory=sub,
                description=f"Test product for {user.username}",
                created_by=user,
                updated_by=user
            )
            prod.save() # This triggers asin_code generation
            
            # Location
            inv = WarehouseInventory.objects.create(
                product=prod,
                location_number=f"LOC-{user.username}-{idx+1}",
                price=Decimal('100.00'),
                carton_piece=10,
                cbm=Decimal('1.5000'),
                created_by=user,
                updated_by=user,
                remark="Initial location"
            )
            
            # Order
            order = Order(
                product=prod,
                location=inv,
                quantity=5, # 5 cartons
                price=inv.price, # 100
                deposit=Decimal('20.00'),
                cbm=inv.cbm, # 1.5
                carton_piece=inv.carton_piece, # 10
                created_by=user,
                order_date=timezone.now().date()
            )
            order.save()
            
            # Verify calculations
            order.refresh_from_db()
            assert order.remaining_to_pay == Decimal('80.00'), f"Remaining amount wrong: {order.remaining_to_pay}"
            assert order.total_cbm == Decimal('7.5000'), f"Total CBM wrong: {order.total_cbm}"
            assert order.total_pieces == 50, f"Total Pieces wrong: {order.total_pieces}"
            
    print("Creating Products, Locations, Orders for Admin...")
    create_plo(admin, admin_cats)
    print("Creating Products, Locations, Orders for User1...")
    create_plo(user1, user1_cats)
    print("Creating Products, Locations, Orders for User2...")
    create_plo(user2, user2_cats)
    
    # 7. Verification Checklist
    print("Verifying List Views (Isolation)...")
    assert filter_products_own(admin).count() == 5
    assert filter_products_own(user1).count() == 5
    assert filter_products_own(user2).count() == 5
    
    assert filter_inventory_own(admin).count() == 5
    assert filter_inventory_own(user1).count() == 5
    assert filter_inventory_own(user2).count() == 5
    
    assert filter_orders_own(admin).count() == 5
    assert filter_orders_own(user1).count() == 5
    assert filter_orders_own(user2).count() == 5
    print("Isolation checks passed!")

    # Summary
    print("--------------------------------------------------")
    print("FINAL SUMMARY REPORT")
    print("--------------------------------------------------")
    print(f"Categories Created: {Category.objects.count()}")
    print(f"Subcategories Created: {SubCategory.objects.count()}")
    print(f"Products Created: {Product.objects.count()}")
    print(f"Locations Created: {WarehouseInventory.objects.count()}")
    print(f"Orders Created: {Order.objects.count()}")
    print(f"Approved Users: {User.objects.filter(is_active=True, is_superuser=False).count()}")
    print(f"Rejected Users: {User.objects.filter(is_active=False).count()}")
    print("Errors Found: 0")
    print("--------------------------------------------------")

seed_and_test()
