from django.urls import path, include
from django.contrib.auth.decorators import login_required
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'sensors'

# Router for ViewSets
router = DefaultRouter()
router.register(r'mqtt-clusters', views.MqttClusterViewSet, basename='mqtt-cluster')

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
    path('api/mqtt/stats/', views.mqtt_statistics, name='mqtt-statistics'),
    path('api/mqtt/delete-hosted/', views.delete_hosted_cluster, name='delete-hosted-cluster'),
    path('api/acls/', views.acl_list_create, name='acl-list-create'),
    path('api/acls/<str:acl_id>/', views.acl_detail, name='acl-detail'),
    
    # MQTT Cluster management
    path('api/', include(router.urls)),
    path('api/mqtt-clusters/<uuid:cluster_uuid>/stats/', views.mqtt_cluster_stats, name='mqtt-cluster-stats'),
    path('api/mqtt-clusters/<uuid:cluster_uuid>/test/', views.mqtt_cluster_test_connection, name='mqtt-cluster-test'),
] 