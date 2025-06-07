from django.urls import path
from django.contrib.auth.decorators import login_required
from . import views

app_name = 'sensors'

urlpatterns = [
    path('dashboard/', login_required(views.dashboard), name='dashboard'),
    path('devices/', login_required(views.device_registration), name='device-registration'),
    path('api/data/', views.SensorDataListView.as_view(), name='sensor-data-list'),
    path('api/dashboard/data/', views.SensorDataListView.as_view(), name='dashboard-data-list'),
    path('api/summary/', views.sensor_data_summary, name='sensor-data-summary'),
    path('api/latest/', views.latest_sensor_data, name='latest-sensor-data'),
    path('api/devices/', views.device_list_create, name='device-list-create'),
    path('api/devices/<str:device_id>/', views.device_detail, name='device-detail'),
    path('api/mqtt/set-password/', views.set_mqtt_password, name='set-mqtt-password'),
    path('api/mqtt/info/', views.user_mqtt_info, name='user-mqtt-info'),
] 