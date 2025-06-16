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
from user.models import MosquittoUser, MosquittoACL, MosquittoSuperuser, UserProfile, DeviceHistory
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
        has_password = False
        
        # Check mosquitto database for actual credentials (this is the source of truth)
        if mqtt_username:
            try:
                from django.db import connections
                cursor = connections['mosquitto'].cursor()
                cursor.execute("SELECT COUNT(*) FROM mosquitto_users WHERE username = %s", [mqtt_username])
                has_password = cursor.fetchone()[0] > 0
            except Exception as e:
                print(f"Error checking MQTT user: {e}")
                has_password = False
        
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

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def acl_list_create(request):
    """List or create MQTT ACL entries for the logged-in user in mosquitto database"""
    
    # Get user's MQTT username
    try:
        profile = request.user.profile
        mqtt_username = profile.mqtt_username
        if not mqtt_username:
            return Response({'error': 'MQTT username not set. Please set MQTT credentials first.'}, status=400)
    except UserProfile.DoesNotExist:
        return Response({'error': 'User profile not found'}, status=404)
    
    if request.method == 'GET':
        try:
            from django.db import connections
            cursor = connections['mosquitto'].cursor()
            cursor.execute("SELECT topic, rw FROM mosquitto_acls WHERE username = %s", [mqtt_username])
            rows = cursor.fetchall()
            
            data = []
            for idx, row in enumerate(rows):
                data.append({
                    'id': f"{mqtt_username}:{row[0]}",  # Use username:topic as unique identifier
                    'topicPattern': row[0],
                    'accessType': row[1]
                })
            
            return Response(data)
            
        except Exception as e:
            print(f"Error fetching ACLs: {e}")
            return Response({'error': 'Failed to fetch ACLs'}, status=500)

    if request.method == 'POST':
        topic = request.data.get('topicPattern')
        access = request.data.get('accessType')
        
        if not topic or access is None:
            return Response({'error': 'topicPattern and accessType required'}, status=400)
            
        try:
            access = int(access)
            if access not in [1, 2, 3, 4]:  # 1=read, 2=write, 3=read/write, 4=subscribe
                raise ValueError()
        except ValueError:
            return Response({'error': 'Invalid accessType. Must be 1(read), 2(write), 3(read/write), or 4(subscribe)'}, status=400)
        
        try:
            from django.db import connections
            cursor = connections['mosquitto'].cursor()
            cursor.execute(
                "INSERT INTO mosquitto_acls (username, topic, rw) VALUES (%s, %s, %s)",
                [mqtt_username, topic, access]
            )
            cursor.execute("COMMIT")
            
            # Return the composite ID
            acl_id = f"{mqtt_username}:{topic}"
            
            return Response({'id': acl_id}, status=201)
            
        except Exception as e:
            print(f"Error creating ACL: {e}")
            return Response({'error': 'Failed to create ACL'}, status=500)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def acl_detail(request, acl_id):
    """Delete specific ACL from mosquitto database"""
    
    # Get user's MQTT username
    try:
        profile = request.user.profile
        mqtt_username = profile.mqtt_username
        if not mqtt_username:
            return Response({'error': 'MQTT username not set'}, status=400)
    except UserProfile.DoesNotExist:
        return Response({'error': 'User profile not found'}, status=404)
    
    try:
        # Parse the composite ID (username:topic)
        if ':' not in acl_id:
            return Response({'error': 'Invalid ACL ID format'}, status=400)
        
        acl_username, topic = acl_id.split(':', 1)
        
        # Verify that the ACL belongs to the current user
        if acl_username != mqtt_username:
            return Response({'error': 'Access denied'}, status=403)
        
        from django.db import connections
        cursor = connections['mosquitto'].cursor()
        
        # Check if the ACL exists
        cursor.execute("SELECT COUNT(*) FROM mosquitto_acls WHERE username = %s AND topic = %s", [mqtt_username, topic])
        if cursor.fetchone()[0] == 0:
            return Response({'error': 'ACL not found'}, status=404)
        
        # Delete the ACL
        cursor.execute("DELETE FROM mosquitto_acls WHERE username = %s AND topic = %s", [mqtt_username, topic])
        cursor.execute("COMMIT")
        
        return Response(status=204)
        
    except Exception as e:
        print(f"Error deleting ACL: {e}")
        return Response({'error': 'Failed to delete ACL'}, status=500)


# MQTT Cluster Management Views

from rest_framework import viewsets
from .models import MqttCluster, MqttTopic, MqttActivity
from .serializers import MqttClusterSerializer, MqttClusterListSerializer, MqttTopicSerializer, MqttActivitySerializer

class MqttClusterViewSet(viewsets.ModelViewSet):
    """ViewSet for managing MQTT clusters"""
    
    permission_classes = [IsAuthenticated]
    lookup_field = 'uuid'
    
    def get_queryset(self):
        """Return clusters for the current user"""
        return MqttCluster.objects.filter(user=self.request.user).order_by('-created_at')
    
    def get_serializer_class(self):
        """Use different serializers for list vs detail views"""
        if self.action == 'list':
            return MqttClusterListSerializer
        return MqttClusterSerializer
    
    def perform_create(self, serializer):
        """Set the user when creating a cluster"""
        serializer.save(user=self.request.user)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mqtt_cluster_stats(request, cluster_uuid):
    """Get detailed statistics for a specific MQTT cluster"""
    
    try:
        cluster = MqttCluster.objects.get(uuid=cluster_uuid, user=request.user)
    except MqttCluster.DoesNotExist:
        return Response({'error': 'Cluster not found'}, status=404)
    
    # Get recent activities
    recent_activities = cluster.activities.order_by('-timestamp')[:20]
    
    # Get topic statistics
    active_topics = cluster.topics.filter(is_active=True).order_by('-last_message_at')
    
    # Calculate some basic stats
    from django.db.models import Sum, Count
    from datetime import datetime, timedelta
    
    # Get activity for different time periods
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)
    
    today_activities = cluster.activities.filter(timestamp__gte=today)
    week_activities = cluster.activities.filter(timestamp__gte=week_ago)
    
    stats = {
        'cluster': MqttClusterSerializer(cluster).data,
        'topic_stats': {
            'active_topics': active_topics.count(),
            'total_messages': cluster.total_messages,
            'total_subscriptions': cluster.total_subscriptions,
        },
        'activity_stats': {
            'today': {
                'total_messages': today_activities.filter(activity_type='publish').count(),
                'connections': today_activities.filter(activity_type='connect').count(),
                'subscriptions': today_activities.filter(activity_type='subscribe').count(),
            },
            'this_week': {
                'total_messages': week_activities.filter(activity_type='publish').count(),
                'connections': week_activities.filter(activity_type='connect').count(),
                'subscriptions': week_activities.filter(activity_type='subscribe').count(),
            }
        },
        'recent_activities': MqttActivitySerializer(recent_activities, many=True).data,
        'active_topics': MqttTopicSerializer(active_topics[:10], many=True).data
    }
    
    return Response(stats)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mqtt_cluster_test_connection(request, cluster_uuid):
    """Test connection to an MQTT cluster"""
    
    try:
        cluster = MqttCluster.objects.get(uuid=cluster_uuid, user=request.user)
    except MqttCluster.DoesNotExist:
        return Response({'error': 'Cluster not found'}, status=404)
    
    # This is a placeholder for actual connection testing
    # In a real implementation, you would use an MQTT client library
    # to test the connection
    
    try:
        import socket
        
        # Simple socket test to check if host is reachable
        sock = socket.create_connection((cluster.host, cluster.port), timeout=5)
        sock.close()
        
        # Log the test activity
        MqttActivity.objects.create(
            cluster=cluster,
            activity_type='connect',
            client_id=f'test_client_{request.user.username}',
            topic_name='$SYS/test'
        )
        
        return Response({
            'status': 'success',
            'message': f'Successfully connected to {cluster.host}:{cluster.port}',
            'connection_url': cluster.connection_url
        })
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': f'Failed to connect: {str(e)}',
            'connection_url': cluster.connection_url
        }, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mqtt_statistics(request):
    """
    Get MQTT statistics for the current user from mosquitto database
    
    PROPOSED REAL TRAFFIC CALCULATION APPROACH:
    
    1. TOPIC STATISTICS:
       - Count unique topics from mosquitto_acls table
       - Track actual active topics from MQTT broker logs (future enhancement)
       - Monitor topic hierarchy and wildcards
    
    2. MESSAGE COUNT:
       - Current: Estimated based on topic count
       - Proposed: Integrate with MQTT broker logging/monitoring
       - Use $SYS/broker/messages/publish/received from broker
       - Store message counts in Django models (MqttActivity table)
    
    3. TRAFFIC CALCULATION:
       - Current: Estimated based on message count * average size
       - Proposed: 
         a) Log actual message sizes in MqttActivity model
         b) Use MQTT broker's $SYS/broker/bytes/sent and $SYS/broker/bytes/received
         c) Implement MQTT client that subscribes to $SYS topics for real stats
         d) Store traffic data with timestamps for historical tracking
    
    4. REAL-TIME ACTIVITY:
       - Current: Generated from ACL patterns
       - Proposed:
         a) Use MQTT broker event hooks/plugins
         b) Log connect/disconnect/publish/subscribe events to MqttActivity
         c) Real-time WebSocket updates to frontend
         d) Parse broker log files for activity extraction
    
    5. IMPLEMENTATION STRATEGY:
       - Phase 1: Current ACL-based estimation (implemented)
       - Phase 2: Add MQTT client for $SYS topic monitoring
       - Phase 3: Integrate broker event logging
       - Phase 4: Real-time activity streaming
    """
    
    try:
        # Get user's MQTT username
        try:
            profile = request.user.profile
            mqtt_username = profile.mqtt_username
            if not mqtt_username:
                return Response({'error': 'MQTT username not set'}, status=400)
        except UserProfile.DoesNotExist:
            return Response({'error': 'User profile not found'}, status=404)
        
        from django.db import connections
        cursor = connections['mosquitto'].cursor()
        
        # Get all ACLs for this user
        cursor.execute("SELECT topic, rw FROM mosquitto_acls WHERE username = %s", [mqtt_username])
        acls = cursor.fetchall()
        
        # Calculate statistics
        unique_topics = set(acl[0] for acl in acls)
        topic_count = len(unique_topics)
        
        # Count different access types
        pub_count = len([acl for acl in acls if acl[1] in [2, 3]])  # Write or Read/Write
        sub_count = len([acl for acl in acls if acl[1] == 4])  # Subscribe
        read_count = len([acl for acl in acls if acl[1] in [1, 3]])  # Read or Read/Write
        
        # Estimate message count based on topics (placeholder calculation)
        estimated_messages = topic_count * 50  # Rough estimate
        
        # Calculate estimated traffic (placeholder)
        traffic_kb = estimated_messages * 0.5  # Assume 0.5KB per message
        
        # Generate recent activity from ACLs
        recent_activities = []
        for i, acl in enumerate(acls[:5]):
            activity_type = 'PUB' if acl[1] in [2, 3] else 'SUB' if acl[1] == 4 else 'READ'
            recent_activities.append({
                'type': activity_type,
                'topic': acl[0],
                'time': f'{(i + 1) * 2}m ago'
            })
        
        stats = {
            'topics': topic_count,
            'messages': estimated_messages,
            'subscriptions': sub_count,
            'publishers': pub_count,
            'readers': read_count,
            'activities': recent_activities,
            'traffic': {
                'today_kb': round(traffic_kb * 0.1, 1),
                'week_kb': round(traffic_kb * 0.7, 1),
                'lifetime_kb': round(traffic_kb * 2.5, 1)
            },
            'acl_count': len(acls)
        }
        
        return Response(stats)
        
    except Exception as e:
        print(f"Error calculating MQTT statistics: {e}")
        return Response({'error': 'Failed to calculate statistics'}, status=500)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_hosted_cluster(request):
    """Delete all MQTT data for the current user (hosted cluster cleanup)"""
    
    try:
        # Get user's MQTT username
        try:
            profile = request.user.profile
            mqtt_username = profile.mqtt_username
            if not mqtt_username:
                return Response({'error': 'No MQTT credentials to delete'}, status=400)
        except UserProfile.DoesNotExist:
            return Response({'error': 'User profile not found'}, status=404)
        
        from django.db import connections
        cursor = connections['mosquitto'].cursor()
        
        # Delete all ACLs for this user
        cursor.execute("DELETE FROM mosquitto_acls WHERE username = %s", [mqtt_username])
        acl_deleted = cursor.rowcount
        
        # Delete user credentials
        cursor.execute("DELETE FROM mosquitto_users WHERE username = %s", [mqtt_username])
        user_deleted = cursor.rowcount
        
        # Delete from superusers if exists
        cursor.execute("DELETE FROM mosquitto_superusers WHERE username = %s", [mqtt_username])
        super_deleted = cursor.rowcount
        
        cursor.execute("COMMIT")
        
        # Clear profile MQTT flags
        profile.mqtt_password_set = False
        profile.mqtt_connected = False
        profile.save()
        
        return Response({
            'message': 'Hosted cluster data deleted successfully',
            'deleted': {
                'acls': acl_deleted,
                'user': user_deleted,
                'superuser': super_deleted
            }
        })
        
    except Exception as e:
        print(f"Error deleting hosted cluster data: {e}")
        return Response({'error': 'Failed to delete hosted cluster data'}, status=500)
