from django.contrib import admin
from .models import UserProfile, DeviceHistory


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'subscription_type', 'mqtt_username', 'mqtt_password_set', 'mqtt_connected', 'device_limit', 'created_at']
    list_filter = ['subscription_type', 'mqtt_password_set', 'mqtt_connected', 'created_at']
    search_fields = ['user__email', 'user__username', 'mqtt_username']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(DeviceHistory)
class DeviceHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'device_id', 'device_name', 'action', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['user__email', 'device_id', 'device_name']
    readonly_fields = ['timestamp']
    ordering = ['-timestamp']