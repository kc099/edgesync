# Generated by Django 5.1.5 on 2025-06-07 16:01

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        (
            "sensors",
            "0002_mosquittosuperuser_mosquittoacl_mosquittouser_device_and_more",
        ),
    ]

    operations = [
        migrations.DeleteModel(
            name="MosquittoACL",
        ),
        migrations.DeleteModel(
            name="MosquittoSuperuser",
        ),
        migrations.AlterUniqueTogether(
            name="useracl",
            unique_together=None,
        ),
        migrations.RemoveField(
            model_name="useracl",
            name="user",
        ),
        migrations.DeleteModel(
            name="MosquittoUser",
        ),
        migrations.DeleteModel(
            name="UserACL",
        ),
    ]
