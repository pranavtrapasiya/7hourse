# Generated migration for ownership fields on image models

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('aps', '0009_rbac_audit_tracking'),
    ]

    operations = [
        migrations.AddField(
            model_name='cartonimage',
            name='uploaded_by',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='carton_images_uploaded',
                to='auth.user'
            ),
        ),
        migrations.AddField(
            model_name='inventoryproductimage',
            name='uploaded_by',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='product_images_uploaded',
                to='auth.user'
            ),
        ),
        migrations.AddField(
            model_name='inventoryvideo',
            name='uploaded_by',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='videos_uploaded',
                to='auth.user'
            ),
        ),
    ]
