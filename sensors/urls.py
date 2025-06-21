from django.urls import path, include
from django.contrib.auth.decorators import login_required
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'sensors'

# Router for ViewSets
router = DefaultRouter()
router.register(r'mqtt-clusters', views.MqttClusterViewSet, basename='mqtt-cluster')

urlpatterns = [
    # MQTT Cluster Management  
    path('api/', include(router.urls)),
    path('api/mqtt-clusters/<uuid:cluster_uuid>/test/', views.mqtt_cluster_test_connection, name='mqtt-cluster-test'),
    
    # MQTT User Management
    path('api/mqtt/set-password/', views.set_mqtt_password, name='set-mqtt-password'),
    path('api/mqtt/user-info/', views.user_mqtt_info, name='user-mqtt-info'),
    path('api/mqtt/delete-hosted/', views.delete_hosted_cluster, name='delete-hosted-cluster'),
    path('api/acls/', views.acl_list_create, name='acl-list-create'),
    path('api/acls/<str:acl_id>/', views.acl_detail, name='acl-detail'),
] 