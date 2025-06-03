from django.shortcuts import render
from django.http import JsonResponse
from rest_framework import generics, filters
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import SensorData
from .serializers import SensorDataSerializer

def dashboard(request):
    """Render the main dashboard page"""
    return render(request, 'dashboard.html')

class SensorDataListView(generics.ListAPIView):
    """API endpoint for retrieving sensor data with filtering and pagination"""
    queryset = SensorData.objects.all()
    serializer_class = SensorDataSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['device_id', 'sensor_type']
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']

@api_view(['GET'])
def sensor_data_summary(request):
    """API endpoint for getting summary statistics of sensor data"""
    from django.db.models import Count, Avg, Max, Min
    
    device_id = request.GET.get('device_id')
    sensor_type = request.GET.get('sensor_type')
    
    queryset = SensorData.objects.all()
    
    if device_id:
        queryset = queryset.filter(device_id=device_id)
    if sensor_type:
        queryset = queryset.filter(sensor_type=sensor_type)
    
    summary = queryset.aggregate(
        total_readings=Count('id'),
        avg_value=Avg('value'),
        max_value=Max('value'),
        min_value=Min('value'),
        latest_reading=Max('timestamp')
    )
    
    # Get unique devices and sensor types
    devices = SensorData.objects.values_list('device_id', flat=True).distinct()
    sensor_types = SensorData.objects.values_list('sensor_type', flat=True).distinct()
    
    return Response({
        'summary': summary,
        'devices': list(devices),
        'sensor_types': list(sensor_types)
    })

@api_view(['GET'])
def latest_sensor_data(request):
    """API endpoint for getting the latest sensor data for each device/sensor combination"""
    from django.db.models import Max
    
    # Get the latest timestamp for each device_id and sensor_type combination
    latest_data = SensorData.objects.values('device_id', 'sensor_type').annotate(
        latest_timestamp=Max('timestamp')
    )
    
    # Get the actual records for these latest timestamps
    latest_readings = []
    for item in latest_data:
        reading = SensorData.objects.filter(
            device_id=item['device_id'],
            sensor_type=item['sensor_type'],
            timestamp=item['latest_timestamp']
        ).first()
        if reading:
            latest_readings.append(reading)
    
    serializer = SensorDataSerializer(latest_readings, many=True)
    return Response(serializer.data)
