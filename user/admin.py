from django.contrib import admin
from .models import (
    UserProfile, DeviceHistory, Organization, OrganizationMember, 
    DashboardTemplate, TemplatePermission
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'subscription_type', 'mqtt_username', 'mqtt_password_set', 'mqtt_connected', 'device_limit', 'created_at']
    list_filter = ['subscription_type', 'mqtt_password_set', 'mqtt_connected', 'created_at']
    search_fields = ['user__email', 'user__username', 'mqtt_username']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(DeviceHistory)
class DeviceHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'device_name', 'device_id', 'action', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['user__email', 'device_name', 'device_id']
    readonly_fields = ['timestamp']
    ordering = ['-timestamp']


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'slug', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'slug', 'owner__email', 'owner__username']
    readonly_fields = ['created_at', 'updated_at']
    prepopulated_fields = {'slug': ('name',)}
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('owner')


@admin.register(OrganizationMember)
class OrganizationMemberAdmin(admin.ModelAdmin):
    list_display = ['organization', 'user', 'role', 'joined_at', 'invited_by']
    list_filter = ['role', 'joined_at']
    search_fields = ['organization__name', 'user__email', 'user__username']
    readonly_fields = ['joined_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('organization', 'user', 'invited_by')


@admin.register(DashboardTemplate)
class DashboardTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization', 'creator', 'is_active', 'update_frequency', 'created_at']
    list_filter = ['is_active', 'created_at', 'update_frequency']
    search_fields = ['name', 'description', 'organization__name', 'creator__email']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'organization', 'creator', 'is_active')
        }),
        ('Configuration', {
            'fields': ('update_frequency', 'connection_timeout', 'layout', 'widgets', 'datasources')
        }),
        ('Flow Configuration', {
            'fields': ('flow_config',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('organization', 'creator')


@admin.register(TemplatePermission)
class TemplatePermissionAdmin(admin.ModelAdmin):
    list_display = ['template', 'user', 'permission_type', 'granted_by', 'granted_at']
    list_filter = ['permission_type', 'granted_at']
    search_fields = ['template__name', 'user__email', 'user__username', 'granted_by__email']
    readonly_fields = ['granted_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('template', 'user', 'granted_by')