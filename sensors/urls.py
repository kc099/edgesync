from django.urls import path
from . import views

app_name = 'sensors'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('api/data/', views.SensorDataListView.as_view(), name='sensor-data-list'),
    path('api/summary/', views.sensor_data_summary, name='sensor-data-summary'),
    path('api/latest/', views.latest_sensor_data, name='latest-sensor-data'),
] 