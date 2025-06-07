from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, filters, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import SensorData, Device
from user.models import MosquittoUser, MosquittoACL, MosquittoSuperuser, UserACL, UserProfile, DeviceHistory
from .serializers import SensorDataSerializer
import json
import secrets
import string


def get_mqtt_username(user):
    """Get MQTT username for a Django user using UserProfile"""
    try:
        profile = user.profile
        return profile.mqtt_username
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user)
        return None

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


@login_required
def device_registration(request):
    """Render the device registration page"""
    return render(request, 'device_registration.html')


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def device_list_create(request):
    """API endpoint for listing and creating devices"""
    
    if request.method == 'GET':
        try:
            # Get devices for the current user
            devices = Device.objects.filter(user=request.user).order_by('-created_at')
            device_data = []
            
            for device in devices:
                device_data.append({
                    'deviceId': device.device_id,
                    'deviceName': device.device_name,
                    'deviceType': device.device_type,
                    'tenantId': device.tenant_id,
                    'isActive': device.is_active,
                    'createdAt': device.created_at.isoformat(),
                    'permissions': ['read', 'write', 'subscribe']  # Default permissions
                })
            
            return Response(device_data)
            
        except Exception as e:
            print(f"Error loading devices: {e}")
            return Response({
                'error': 'Failed to load devices'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    elif request.method == 'POST':
        try:
            # Parse request data properly
            if hasattr(request, 'data'):
                data = request.data
            else:
                data = json.loads(request.body)
            
            # Get or create user profile
            try:
                profile = request.user.profile
            except UserProfile.DoesNotExist:
                profile = UserProfile.objects.create(user=request.user)
            
            # Check if user can add more devices
            if not profile.can_add_device():
                return Response({
                    'error': f'Device limit reached ({profile.device_limit} devices). Upgrade your subscription to add more devices.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate required fields
            required_fields = ['deviceId', 'deviceName', 'deviceType', 'tenantId']
            for field in required_fields:
                if not data.get(field):
                    return Response({
                        'error': f'{field} is required'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if device ID already exists for this user
            if Device.objects.filter(device_id=data['deviceId'], user=request.user).exists():
                return Response({
                    'error': 'Device ID already exists'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create device
            device = Device.objects.create(
                device_id=data['deviceId'],
                device_name=data['deviceName'],
                device_type=data['deviceType'],
                tenant_id=data['tenantId'],
                user=request.user
            )
            
            # Get user's MQTT username
            mqtt_username = profile.mqtt_username
            if not mqtt_username:
                return Response({
                    'error': 'Please set your MQTT credentials first before registering devices'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create ACLs for the device topics
            permissions = data.get('permissions', ['read', 'write', 'subscribe'])
            topic_base = f"iot/{data['tenantId']}/{data['deviceId']}"
            
            acl_mappings = {
                'read': 1,
                'write': 2, 
                'subscribe': 4
            }
            
            # Create ACLs for the device topics using raw SQL to avoid ORM issues
            from django.db import connections
            
            try:
                cursor = connections['mosquitto'].cursor()
                
                for permission in permissions:
                    if permission in acl_mappings:
                        # Create ACL for data topic
                        cursor.execute(
                            "INSERT IGNORE INTO mosquitto_acls (username, topic, rw) VALUES (%s, %s, %s)",
                            [mqtt_username, f"{topic_base}/data", acl_mappings[permission]]
                        )
                        
                        # Create ACL for commands topic (if write permission)
                        if permission in ['write', 'subscribe']:
                            cursor.execute(
                                "INSERT IGNORE INTO mosquitto_acls (username, topic, rw) VALUES (%s, %s, %s)",
                                [mqtt_username, f"{topic_base}/commands", acl_mappings[permission]]
                            )
                        
                        # Create ACL for status topic
                        cursor.execute(
                            "INSERT IGNORE INTO mosquitto_acls (username, topic, rw) VALUES (%s, %s, %s)",
                            [mqtt_username, f"{topic_base}/status", acl_mappings[permission]]
                        )
                
                # Commit the changes
                cursor.execute("COMMIT")
                
            except Exception as e:
                print(f"Error creating MQTT ACLs: {e}")
                # Continue without MQTT ACLs if database connection fails
            
            # Create UserACL records for easier management
            UserACL.objects.get_or_create(
                user=request.user,
                topic_pattern=f"{topic_base}/+",
                access_type=UserACL.ACCESS_READWRITE
            )
            
            # Log device creation
            DeviceHistory.objects.create(
                user=request.user,
                device_id=device.device_id,
                device_name=device.device_name,
                action='created',
                details={
                    'device_type': device.device_type,
                    'tenant_id': device.tenant_id,
                    'permissions': permissions
                }
            )
            
            return Response({
                'message': 'Device registered successfully',
                'deviceId': device.device_id
            }, status=status.HTTP_201_CREATED)
            
        except json.JSONDecodeError:
            return Response({
                'error': 'Invalid JSON data'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def device_detail(request, device_id):
    """API endpoint for retrieving, updating, and deleting a specific device"""
    
    try:
        device = Device.objects.get(device_id=device_id, user=request.user)
    except Device.DoesNotExist:
        return Response({
            'error': 'Device not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        device_data = {
            'deviceId': device.device_id,
            'deviceName': device.device_name,
            'deviceType': device.device_type,
            'tenantId': device.tenant_id,
            'isActive': device.is_active,
            'createdAt': device.created_at.isoformat(),
            'permissions': ['read', 'write', 'subscribe']
        }
        return Response(device_data)
    
    elif request.method == 'PATCH':
        try:
            data = json.loads(request.body)
            
            # Update allowed fields
            if 'deviceName' in data:
                device.device_name = data['deviceName']
            if 'isActive' in data:
                device.is_active = data['isActive']
            
            device.save()
            
            return Response({
                'message': 'Device updated successfully'
            })
            
        except json.JSONDecodeError:
            return Response({
                'error': 'Invalid JSON data'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    elif request.method == 'DELETE':
        try:
            # Delete related ACLs using raw SQL
            try:
                from django.db import connections
                cursor = connections['mosquitto'].cursor()
                mqtt_username = get_mqtt_username(request.user)
                if mqtt_username:  # Only delete ACLs if user has MQTT username
                    topic_base = f"iot/{device.tenant_id}/{device.device_id}"
                    
                    # Delete ACLs for this device's topics
                    cursor.execute(
                        "DELETE FROM mosquitto_acls WHERE username = %s AND topic LIKE %s",
                        [mqtt_username, f"{topic_base}%"]
                    )
                cursor.execute("COMMIT")
                
            except Exception as e:
                print(f"Error deleting MQTT ACLs: {e}")
                # Continue without MQTT ACL deletion if database connection fails
            
            # Delete UserACL records
            UserACL.objects.filter(
                user=request.user,
                topic_pattern__startswith=topic_base
            ).delete()
            
            # Log device deletion before deleting
            DeviceHistory.objects.create(
                user=request.user,
                device_id=device.device_id,
                device_name=device.device_name,
                action='deleted',
                details={
                    'device_type': device.device_type,
                    'tenant_id': device.tenant_id
                }
            )
            
            # Delete device
            device.delete()
            
            return Response({
                'message': 'Device deleted successfully'
            })
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_mqtt_password(request):
    """API endpoint for setting user's MQTT password and username"""
    
    try:
        # Parse request data
        if hasattr(request, 'data'):
            data = request.data
        else:
            data = json.loads(request.body)
        
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or len(username) < 3:
            return Response({
                'error': 'Username must be at least 3 characters long'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not password or len(password) < 8:
            return Response({
                'error': 'Password must be at least 8 characters long'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate username format (alphanumeric and underscores only)
        if not username.replace('_', '').isalnum():
            return Response({
                'error': 'Username can only contain letters, numbers, and underscores'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if username already exists in mosquitto database
        try:
            from django.db import connections
            cursor = connections['mosquitto'].cursor()
            cursor.execute("SELECT COUNT(*) FROM mosquitto_users WHERE username = %s", [username])
            if cursor.fetchone()[0] > 0:
                return Response({
                    'error': 'Username already exists. Please choose a different username.'
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"Error checking username availability: {e}")
            return Response({
                'error': 'Unable to verify username availability'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Get or create user profile
        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            profile = UserProfile.objects.create(user=request.user)
        
        # Set the custom username
        profile.mqtt_username = username
        
        hashed_password = MosquittoUser.create_pbkdf2_password(password)
        
        # Create MQTT user using raw SQL
        try:
            cursor.execute(
                "INSERT INTO mosquitto_users (username, password) VALUES (%s, %s)",
                [username, hashed_password]
            )
            cursor.execute("COMMIT")
            
            # Update profile
            profile.mqtt_password_set = True
            profile.save()
            
        except Exception as e:
            print(f"Error creating MQTT user: {e}")
            return Response({
                'error': 'Failed to create MQTT user'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'username': username,
            'message': 'MQTT credentials set successfully'
        })
        
    except json.JSONDecodeError:
        return Response({
            'error': 'Invalid request format'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        print(f"Unexpected error in set_mqtt_password: {e}")
        return Response({
            'error': f'An unexpected error occurred: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_mqtt_info(request):
    """API endpoint for getting user's MQTT connection information"""
    
    try:
        # Get or create user profile
        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            profile = UserProfile.objects.create(user=request.user)
        
        # Get MQTT username (could be None if not set yet)
        mqtt_username = profile.mqtt_username if profile.mqtt_username else None
        has_password = profile.mqtt_password_set
        
        # Double-check with database if username exists
        if mqtt_username and has_password:
            try:
                from django.db import connections
                cursor = connections['mosquitto'].cursor()
                cursor.execute("SELECT COUNT(*) FROM mosquitto_users WHERE username = %s", [mqtt_username])
                has_password = cursor.fetchone()[0] > 0
            except Exception as e:
                print(f"Error checking MQTT user: {e}")
                # Use profile setting as fallback
        
        # Get user's devices for topic examples
        devices = Device.objects.filter(user=request.user)[:3]
        topic_examples = []
        
        for device in devices:
            topic_examples.append({
                'device': device.device_name,
                'topics': [
                    f"iot/{device.tenant_id}/{device.device_id}/data",
                    f"iot/{device.tenant_id}/{device.device_id}/commands",
                    f"iot/{device.tenant_id}/{device.device_id}/status"
                ]
            })
        
        return Response({
            'username': mqtt_username,
            'hasPassword': has_password,
            'passwordSet': profile.mqtt_password_set,
            'connected': profile.mqtt_connected,
            'subscriptionType': profile.subscription_type,
            'deviceLimit': profile.device_limit,
            'deviceCount': Device.objects.filter(user=request.user).count(),
            'broker': {
                'host': '13.203.165.247',
                'port': 1883,
                'websocketPort': 1884
            },
            'topicExamples': topic_examples
        })
        
    except Exception as e:
        print(f"Error in user_mqtt_info: {e}")
        return Response({
            'error': 'Failed to load MQTT information'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
