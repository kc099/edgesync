from django.contrib import admin
from .models import SensorData

@admin.register(SensorData)
class SensorDataAdmin(admin.ModelAdmin):
    list_display = ['device_id', 'sensor_type', 'value', 'unit', 'timestamp']
    list_filter = ['device_id', 'sensor_type', 'timestamp']
    search_fields = ['device_id', 'sensor_type']
    readonly_fields = ['timestamp']
    ordering = ['-timestamp']
    
    def has_add_permission(self, request):
        # Prevent manual addition through admin (data should come from ESP32)
        return False
