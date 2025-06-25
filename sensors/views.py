from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, filters, status, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.openapi import OpenApiTypes
from .models import MqttCluster, MqttTopic, MqttActivity, Device
from user.models import MosquittoUser, UserProfile, Organization
from .serializers import (
    MqttClusterSerializer, MqttClusterListSerializer, 
    MqttTopicSerializer, MqttActivitySerializer, ACLSerializer,
    MqttPasswordSerializer, DeviceSerializer, DeviceListSerializer,
    DeviceCreateSerializer, DeviceUpdateSerializer, DeviceProjectAssignmentSerializer
)
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




















@extend_schema(
    operation_id='set_mqtt_password',
    tags=['MQTT'],
    summary='Set MQTT Password',
    description='Set user MQTT credentials',
    request=MqttPasswordSerializer,
    responses={
        200: {
            'type': 'object',
            'properties': {
                'username': {'type': 'string'},
                'message': {'type': 'string'}
            }
        },
        400: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'}
            }
        }
    }
)
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
            
            # Create or update hosted cluster entry
            hosted_cluster, created = MqttCluster.objects.get_or_create(
                user=request.user,
                cluster_type='hosted',
                defaults={
                    'name': 'Free #1',
                    'host': '13.203.165.247',
                    'port': 1883,
                    'username': username,
                    'password': password,
                }
            )
            
            if not created:
                # Update existing hosted cluster with new credentials
                hosted_cluster.username = username
                hosted_cluster.password = password
                hosted_cluster.save()
            
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


@extend_schema(
    operation_id='list_acl',
    tags=['MQTT ACL'],
    summary='List ACL Entries',
    description='List MQTT ACL entries for the current user',
    responses={
        200: {
            'type': 'array',
            'items': ACLSerializer
        },
        400: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'}
            }
        }
    },
    methods=['GET']
)
@extend_schema(
    operation_id='create_acl',
    tags=['MQTT ACL'],
    summary='Create ACL Entry',
    description='Create a new MQTT ACL entry',
    request=ACLSerializer,
    responses={
        201: {
            'type': 'object',
            'properties': {
                'id': {'type': 'string'}
            }
        },
        400: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'}
            }
        }
    },
    methods=['POST']
)
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

@extend_schema(
    operation_id='delete_acl',
    tags=['MQTT ACL'],
    summary='Delete ACL Entry',
    description='Delete a specific MQTT ACL entry',
    responses={
        204: {
            'description': 'ACL deleted successfully'
        },
        400: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'}
            }
        },
        403: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'}
            }
        },
        404: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'}
            }
        }
    }
)
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

@extend_schema_view(
    list=extend_schema(
        operation_id='list_mqtt_clusters',
        tags=['MQTT'],
        summary='List MQTT Clusters',
        description='Retrieve all MQTT clusters for the current user'
    ),
    create=extend_schema(
        operation_id='create_mqtt_cluster',
        tags=['MQTT'],
        summary='Create MQTT Cluster',
        description='Create a new MQTT cluster configuration'
    ),
    retrieve=extend_schema(
        operation_id='get_mqtt_cluster',
        tags=['MQTT'],
        summary='Get MQTT Cluster',
        description='Retrieve a specific MQTT cluster by UUID'
    ),
    update=extend_schema(
        operation_id='update_mqtt_cluster',
        tags=['MQTT'],
        summary='Update MQTT Cluster',
        description='Update an MQTT cluster configuration'
    ),
    partial_update=extend_schema(
        operation_id='partial_update_mqtt_cluster',
        tags=['MQTT'],
        summary='Partially Update MQTT Cluster',
        description='Partially update an MQTT cluster configuration'
    ),
    destroy=extend_schema(
        operation_id='delete_mqtt_cluster',
        tags=['MQTT'],
        summary='Delete MQTT Cluster',
        description='Delete an MQTT cluster and clean up associated credentials'
    ),
)
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
    
    def destroy(self, request, *args, **kwargs):
        """Custom delete logic for hosted clusters"""
        cluster = self.get_object()
        
        # If it's a hosted cluster, also clean up mosquitto credentials
        if cluster.cluster_type == 'hosted':
            try:
                # Get user's MQTT username from profile
                profile = request.user.profile
                mqtt_username = profile.mqtt_username
                
                print(f"Deleting hosted cluster for user: {request.user.username}, mqtt_username: {mqtt_username}")
                
                if mqtt_username:
                    from django.db import connections
                    cursor = connections['mosquitto'].cursor()
                    
                    # First get the user_id from users table
                    cursor.execute("SELECT id FROM users WHERE username = %s", [mqtt_username])
                    user_result = cursor.fetchone()
                    
                    if user_result:
                        user_id = user_result[0]
                        print(f"Found user_id {user_id} for username {mqtt_username}")
                        
                        # Delete all ACLs for this user (from real table, not view)
                        cursor.execute("DELETE FROM user_acls WHERE user_id = %s", [user_id])
                        acl_count = cursor.rowcount
                        print(f"Deleted {acl_count} ACL entries for user_id {user_id}")
                        
                        # Delete user credentials (from real table, not view)
                        cursor.execute("DELETE FROM users WHERE id = %s", [user_id])
                        user_count = cursor.rowcount
                        print(f"Deleted {user_count} user entries for user_id {user_id}")
                        
                        # Delete from superusers if exists (this might be a real table)
                        cursor.execute("DELETE FROM mosquitto_superusers WHERE username = %s", [mqtt_username])
                        super_count = cursor.rowcount
                        print(f"Deleted {super_count} superuser entries for {mqtt_username}")
                        
                        cursor.execute("COMMIT")
                    else:
                        print(f"User {mqtt_username} not found in users table")
                    
                    # Clear profile MQTT flags
                    profile.mqtt_password_set = False
                    profile.mqtt_connected = False
                    profile.mqtt_username = None  # Clear the username too
                    profile.save()
                    print(f"Profile flags cleared for {request.user.username}")
                else:
                    print(f"No MQTT username found for user {request.user.username}")
                    
            except Exception as e:
                print(f"Error cleaning up hosted cluster mosquitto data: {e}")
                import traceback
                traceback.print_exc()
        
        # Delete the cluster record
        return super().destroy(request, *args, **kwargs)


@extend_schema(
    operation_id='test_mqtt_connection',
    tags=['MQTT'],
    summary='Test MQTT Connection',
    description='Test connection to an MQTT cluster',
    request={
        'type': 'object',
        'properties': {
            'username': {'type': 'string', 'description': 'MQTT username'},
            'password': {'type': 'string', 'description': 'MQTT password'}
        }
    },
    responses={
        200: {
            'type': 'object',
            'properties': {
                'status': {'type': 'string'},
                'message': {'type': 'string'},
                'details': {'type': 'object'}
            }
        },
        400: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'}
            }
        },
        404: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'}
            }
        }
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mqtt_cluster_test_connection(request, cluster_uuid):
    """Test actual MQTT connection to a cluster with proper MQTT client"""
    
    try:
        cluster = MqttCluster.objects.get(uuid=cluster_uuid, user=request.user)
    except MqttCluster.DoesNotExist:
        return Response({'error': 'Cluster not found'}, status=404)
    
    try:
        # Get credentials from request
        username = request.data.get('username') if request.data.get('username') else cluster.username
        password = request.data.get('password') if request.data.get('password') else cluster.password
        
        # For hosted clusters with placeholder password, ask user to provide password for testing
        if cluster.cluster_type == 'hosted' and (not password or password == '[encrypted]'):
            if not request.data.get('password'):
                return Response({
                    'status': 'error', 
                    'message': 'Please provide your MQTT password for connection testing'
                }, status=400)
            password = request.data.get('password')
        
        if not username or not password:
            return Response({
                'status': 'error', 
                'message': 'Username and password required for testing'
            }, status=400)
        
        # Test actual MQTT connection
        import paho.mqtt.client as mqtt
        import threading
        import time
        
        connection_result = {'success': False, 'error': None, 'message': None}
        connection_event = threading.Event()
        
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                connection_result['success'] = True
                connection_result['message'] = f'Successfully connected to {cluster.host}:{cluster.port}'
            else:
                connection_result['success'] = False
                connection_result['error'] = f'MQTT connection failed with code {rc}'
            connection_event.set()
        
        def on_disconnect(client, userdata, rc):
            pass
        
        # Create MQTT client
        client = mqtt.Client(client_id=f'test_client_{request.user.username}_{int(time.time())}')
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        
        # Set credentials
        if username and password:
            client.username_pw_set(username, password)
        
        try:
            # Connect to broker
            client.connect(cluster.host, cluster.port, 60)
            client.loop_start()
            
            # Wait for connection result (max 10 seconds)
            if connection_event.wait(timeout=10):
                client.disconnect()
                client.loop_stop()
                
                if connection_result['success']:
                    # Log successful test activity
                    MqttActivity.objects.create(
                        cluster=cluster,
                        activity_type='connect',
                        client_id=f'test_client_{request.user.username}',
                        topic_name='$SYS/test'
                    )
                    
                    return Response({
                        'status': 'success',
                        'message': connection_result['message'],
                        'connection_url': cluster.connection_url
                    })
                else:
                    return Response({
                        'status': 'error',
                        'message': connection_result['error'],
                        'connection_url': cluster.connection_url
                    }, status=400)
            else:
                client.disconnect()
                client.loop_stop()
                return Response({
                    'status': 'error',
                    'message': 'Connection timeout - broker not responding',
                    'connection_url': cluster.connection_url
                }, status=400)
                
        except Exception as mqtt_error:
            return Response({
                'status': 'error',
                'message': f'Failed to connect: {str(mqtt_error)}',
                'connection_url': cluster.connection_url
            }, status=400)
        
    except Exception as e:
        return Response({
            'status': 'error',
            'message': f'Test failed: {str(e)}'
        }, status=500)


@extend_schema(
    operation_id='get_user_mqtt_info',
    tags=['MQTT'],
    summary='Get User MQTT Info',
    description='Get current user MQTT connection information',
    responses={
        200: {
            'type': 'object',
            'properties': {
                'mqtt_username': {'type': 'string'},
                'hosted_cluster': {'type': 'object'},
                'status': {'type': 'string'}
            }
        }
    }
)
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
        
        return Response({
            'username': mqtt_username,
            'hasPassword': has_password,
            'passwordSet': profile.mqtt_password_set,
            'connected': profile.mqtt_connected,
            'subscriptionType': profile.subscription_type,
            'deviceLimit': profile.device_limit,
            'broker': {
                'host': '13.203.165.247',
                'port': 1883,
                'websocketPort': 1884
            }
        })
        
    except Exception as e:
        print(f"Error in user_mqtt_info: {e}")
        return Response({
            'error': 'Failed to load MQTT information'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@extend_schema(
    operation_id='delete_hosted_cluster',
    tags=['MQTT'],
    summary='Delete Hosted Cluster',
    description='Delete the hosted MQTT cluster and clean up credentials',
    responses={
        200: {
            'type': 'object',
            'properties': {
                'message': {'type': 'string'}
            }
        },
        404: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'}
            }
        }
    }
)
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


# Device Management Views

@extend_schema_view(
    list=extend_schema(
        operation_id='list_devices',
        tags=['Devices'],
        summary='List Devices',
        description='Retrieve all devices for the current user\'s organizations. Can be filtered by organization or project.',
        parameters=[
            OpenApiParameter(
                name='organization',
                description='Filter devices by organization ID',
                required=False,
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
            ),
            OpenApiParameter(
                name='project_uuid',
                description='Filter devices by project UUID',
                required=False,
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
            ),
        ]
    ),
    create=extend_schema(
        operation_id='create_device',
        tags=['Devices'],
        summary='Create Device',
        description='Create a new IoT device with authentication token'
    ),
    retrieve=extend_schema(
        operation_id='get_device',
        tags=['Devices'],
        summary='Get Device',
        description='Retrieve a specific device by UUID'
    ),
    update=extend_schema(
        operation_id='update_device',
        tags=['Devices'],
        summary='Update Device',
        description='Update a device configuration'
    ),
    partial_update=extend_schema(
        operation_id='partial_update_device',
        tags=['Devices'],
        summary='Partially Update Device',
        description='Partially update a device configuration'
    ),
    destroy=extend_schema(
        operation_id='delete_device',
        tags=['Devices'],
        summary='Delete Device',
        description='Delete a device and clean up associated data'
    ),
)
class DeviceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing IoT devices.
    Provides CRUD operations and project assignment functionality.
    """
    
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'is_active', 'organization']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'updated_at', 'last_seen']
    ordering = ['-created_at']
    lookup_field = 'uuid'
    
    def get_queryset(self):
        user = self.request.user
        # Get organizations where user is a member
        user_orgs = Organization.objects.filter(members__user=user)
        queryset = Device.objects.filter(organization__in=user_orgs)
        
        # Filter by organization if specified
        org_id = self.request.query_params.get('organization')
        if org_id:
            queryset = queryset.filter(organization_id=org_id)
        
        # Filter by project if specified
        project_uuid = self.request.query_params.get('project_uuid')
        if project_uuid:
            queryset = queryset.filter(projects__uuid=project_uuid)
        
        return queryset.distinct()
    
    def get_serializer_class(self):
        if self.action == 'list':
            return DeviceListSerializer
        elif self.action == 'create':
            return DeviceCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return DeviceUpdateSerializer
        return DeviceSerializer
    
    def perform_create(self, serializer):
        # Validate organization membership
        organization = serializer.validated_data.get('organization')
        if not organization.members.filter(user=self.request.user).exists():
            raise serializers.ValidationError("You are not a member of this organization")
        
        serializer.save(creator=self.request.user)
    
    def perform_update(self, serializer):
        # Check if user can modify this device
        device = self.get_object()
        if not device.organization.members.filter(user=self.request.user).exists():
            raise serializers.ValidationError("You don't have permission to modify this device")
        
        serializer.save()
    
    def perform_destroy(self, instance):
        # Check if user can delete this device
        if not instance.organization.members.filter(user=self.request.user).exists():
            raise serializers.ValidationError("You don't have permission to delete this device")
        
        # TODO: Add cleanup for associated sensor data if needed
        instance.delete()
    
    @extend_schema(
        operation_id='assign_device_to_project',
        tags=['Devices'],
        summary='Assign Device to Project',
        description='Assign a device to a project within the same organization',
        request=DeviceProjectAssignmentSerializer,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'device_uuid': {'type': 'string'},
                    'project_uuid': {'type': 'string'}
                }
            },
            400: {'type': 'object', 'properties': {'error': {'type': 'string'}}},
            403: {'type': 'object', 'properties': {'error': {'type': 'string'}}},
            404: {'type': 'object', 'properties': {'error': {'type': 'string'}}}
        }
    )
    @action(detail=True, methods=['post'])
    def assign_project(self, request, uuid=None):
        """Assign device to a project"""
        device = self.get_object()
        
        # Check permission
        if not device.organization.members.filter(user=request.user).exists():
            return Response({'error': 'Permission denied'}, status=403)
        
        serializer = DeviceProjectAssignmentSerializer(
            data=request.data,
            context={'device': device}
        )
        
        if serializer.is_valid():
            project_uuid = serializer.validated_data['project_uuid']
            
            try:
                from user.models import Project
                project = Project.objects.get(
                    uuid=project_uuid,
                    organization=device.organization
                )
                
                device.assign_to_project(project)
                
                return Response({
                    'message': 'Device assigned to project successfully',
                    'device_uuid': str(device.uuid),
                    'project_uuid': str(project.uuid)
                })
                
            except Project.DoesNotExist:
                return Response({'error': 'Project not found'}, status=404)
            except Exception as e:
                return Response({'error': str(e)}, status=400)
        
        return Response(serializer.errors, status=400)
    
    @extend_schema(
        operation_id='unassign_device_from_project',
        tags=['Devices'],
        summary='Unassign Device from Project',
        description='Remove device assignment from a project',
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'message': {'type': 'string'},
                    'device_uuid': {'type': 'string'},
                    'project_uuid': {'type': 'string'}
                }
            },
            403: {'type': 'object', 'properties': {'error': {'type': 'string'}}},
            404: {'type': 'object', 'properties': {'error': {'type': 'string'}}}
        }
    )
    @action(detail=True, methods=['delete'], url_path='assign-project/(?P<project_uuid>[^/.]+)')
    def unassign_project(self, request, uuid=None, project_uuid=None):
        """Remove device assignment from a project"""
        device = self.get_object()
        
        # Check permission
        if not device.organization.members.filter(user=request.user).exists():
            return Response({'error': 'Permission denied'}, status=403)
        
        try:
            from user.models import Project
            project = Project.objects.get(
                uuid=project_uuid,
                organization=device.organization
            )
            
            device.unassign_from_project(project)
            
            return Response({
                'message': 'Device unassigned from project successfully',
                'device_uuid': str(device.uuid),
                'project_uuid': str(project.uuid)
            })
            
        except Project.DoesNotExist:
            return Response({'error': 'Project not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=400)


@extend_schema(
    operation_id='regenerate_device_token',
    tags=['Devices'],
    summary='Regenerate Device Token',
    description='Generate a new authentication token for a device',
    responses={
        200: {
            'type': 'object',
            'properties': {
                'message': {'type': 'string'},
                'token': {'type': 'string'},
                'device_uuid': {'type': 'string'}
            }
        },
        403: {'type': 'object', 'properties': {'error': {'type': 'string'}}},
        404: {'type': 'object', 'properties': {'error': {'type': 'string'}}}
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def regenerate_device_token(request, device_uuid):
    """Regenerate authentication token for a device"""
    try:
        device = Device.objects.get(uuid=device_uuid)
        
        # Check permission
        if not device.organization.members.filter(user=request.user).exists():
            return Response({'error': 'Permission denied'}, status=403)
        
        # Generate new token
        device.token = secrets.token_urlsafe(32)
        device.save()
        
        return Response({
            'message': 'Device token regenerated successfully',
            'token': device.token,
            'device_uuid': str(device.uuid)
        })
        
    except Device.DoesNotExist:
        return Response({'error': 'Device not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=400)
