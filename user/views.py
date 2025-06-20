from django.shortcuts import render
from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db.models import Q
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.openapi import OpenApiTypes
import json

from .serializers import (
    LoginSerializer, SignupSerializer, UserSerializer,
    OrganizationSerializer, OrganizationMemberSerializer,
    DashboardTemplateSerializer, TemplatePermissionSerializer,
    CreateOrganizationSerializer, CreateDashboardTemplateSerializer,
    ProjectSerializer, CreateProjectSerializer
)
from .utils.encryption import encryption_manager
from .models import UserProfile, Organization, OrganizationMember, DashboardTemplate, TemplatePermission, Project


def get_tokens_for_user(user):
    """Generate JWT tokens for user"""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


@extend_schema(
    operation_id='get_public_key',
    tags=['Authentication'],
    summary='Get RSA Public Key',
    description='Retrieve the RSA public key for encrypting authentication data',
    responses={
        200: {
            'type': 'object',
            'properties': {
                'public_key': {'type': 'string', 'description': 'RSA public key in PEM format'},
                'status': {'type': 'string', 'description': 'Operation status'}
            }
        },
        500: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'status': {'type': 'string'}
            }
        }
    }
)
@api_view(['GET'])
@permission_classes([AllowAny])
def public_key_view(request):
    """Get RSA public key for encryption"""
    try:
        public_key_pem = encryption_manager.get_public_key_pem()
        return Response({
            'public_key': public_key_pem,
            'status': 'success'
        })
    except Exception as e:
        return Response({
            'error': 'Failed to retrieve public key',
            'status': 'error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    operation_id='user_login',
    tags=['Authentication'],
    summary='User Login',
    description='Authenticate user with encrypted credentials and receive JWT tokens',
    request={
        'type': 'object',
        'properties': {
            'data': {'type': 'string', 'description': 'Encrypted login data'},
            'key': {'type': 'string', 'description': 'Encrypted AES key'},
            'iv': {'type': 'string', 'description': 'Initialization vector'}
        },
        'required': ['data', 'key', 'iv'],
        'example': {
            'data': 'encrypted_login_data_here',
            'key': 'encrypted_aes_key_here',
            'iv': 'initialization_vector_here'
        }
    },
    responses={
        200: {
            'type': 'object',
            'properties': {
                'token': {'type': 'string', 'description': 'JWT access token'},
                'refresh': {'type': 'string', 'description': 'JWT refresh token'},
                'user': {'type': 'object', 'description': 'User profile data'},
                'status': {'type': 'string', 'description': 'Operation status'}
            }
        },
        400: {
            'type': 'object',
            'properties': {
                'error': {'type': 'object'},
                'status': {'type': 'string'}
            }
        },
        500: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'status': {'type': 'string'}
            }
        }
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """Login user with encrypted credentials only"""
    try:
        data = request.data
        
        # Check if this is encrypted data
        if 'data' not in data or 'key' not in data or 'iv' not in data:
            return Response({
                'error': 'Encrypted authentication required. Please use a secure client.',
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Decrypt the data
        decrypted_data = encryption_manager.decrypt_request_data(data)
        if not decrypted_data:
            return Response({
                'error': 'Failed to decrypt login data',
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate using serializer
        serializer = LoginSerializer(data=decrypted_data)
        
        if serializer.is_valid():
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']
            
            # Authenticate user
            user = authenticate(username=email, password=password)
            if user:
                # Generate JWT tokens
                refresh = RefreshToken.for_user(user)
                access_token = refresh.access_token
                
                return Response({
                    'token': str(access_token),
                    'refresh': str(refresh),
                    'user': UserSerializer(user).data,
                    'status': 'success'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': {'non_field_errors': ['Invalid email or password.']},
                    'status': 'error'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                'error': serializer.errors,
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        return Response({
            'error': 'Authentication failed',
            'status': 'error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    operation_id='user_signup',
    tags=['Authentication'],
    summary='User Registration',
    description='Register a new user with encrypted credentials and receive JWT tokens',
    request={
        'type': 'object',
        'properties': {
            'data': {'type': 'string', 'description': 'Encrypted registration data'},
            'key': {'type': 'string', 'description': 'Encrypted AES key'},
            'iv': {'type': 'string', 'description': 'Initialization vector'}
        },
        'required': ['data', 'key', 'iv'],
        'example': {
            'data': 'encrypted_registration_data_here',
            'key': 'encrypted_aes_key_here',
            'iv': 'initialization_vector_here'
        }
    },
    responses={
        201: {
            'type': 'object',
            'properties': {
                'token': {'type': 'string', 'description': 'JWT access token'},
                'refresh': {'type': 'string', 'description': 'JWT refresh token'},
                'user': {'type': 'object', 'description': 'User profile data'},
                'status': {'type': 'string', 'description': 'Operation status'}
            }
        },
        400: {
            'type': 'object',
            'properties': {
                'error': {'type': 'object'},
                'status': {'type': 'string'}
            }
        },
        500: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'status': {'type': 'string'}
            }
        }
    }
)
@api_view(['POST'])
@permission_classes([AllowAny])
def signup_view(request):
    """Register new user with encrypted credentials only"""
    try:
        data = request.data
        
        # Check if this is encrypted data
        if 'data' not in data or 'key' not in data or 'iv' not in data:
            return Response({
                'error': 'Encrypted authentication required. Please use a secure client.',
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Decrypt the data
        decrypted_data = encryption_manager.decrypt_request_data(data)
        if not decrypted_data:
            return Response({
                'error': 'Failed to decrypt registration data',
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate using serializer
        serializer = SignupSerializer(data=decrypted_data)
        if serializer.is_valid():
            user = serializer.save()
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token
            
            return Response({
                'token': str(access_token),
                'refresh': str(refresh),
                'user': UserSerializer(user).data,
                'status': 'success'
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'error': serializer.errors,
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        return Response({
            'error': 'Registration failed',
            'status': 'error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    operation_id='user_logout',
    tags=['Authentication'],
    summary='User Logout',
    description='Logout user by blacklisting the refresh token',
    request={
        'type': 'object',
        'properties': {
            'refresh_token': {'type': 'string', 'description': 'JWT refresh token to blacklist'}
        },
        'required': ['refresh_token']
    },
    responses={
        200: {
            'type': 'object',
            'properties': {
                'message': {'type': 'string'},
                'status': {'type': 'string'}
            }
        },
        400: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'status': {'type': 'string'}
            }
        }
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Logout user by blacklisting refresh token"""
    try:
        refresh_token = request.data.get('refresh_token')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({
                'message': 'Successfully logged out',
                'status': 'success'
            })
        else:
            return Response({
                'error': 'Refresh token required',
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'error': 'Logout failed',
            'status': 'error'
        }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    operation_id='get_user_profile',
    tags=['Users'],
    summary='Get User Profile',
    description='Retrieve the current user\'s profile information',
    responses={
        200: {
            'type': 'object',
            'properties': {
                'user': {'type': 'object', 'description': 'User profile data'},
                'status': {'type': 'string'}
            }
        },
        401: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'status': {'type': 'string'}
            }
        }
    }
)
@api_view(['GET'])
def profile_view(request):
    """Get user profile - requires authentication"""
    if request.user.is_authenticated:
        return Response({
            'user': UserSerializer(request.user).data,
            'status': 'success'
        })
    else:
        return Response({
            'error': 'Authentication required',
            'status': 'error'
        }, status=status.HTTP_401_UNAUTHORIZED)


# Organization Management Views

@extend_schema(
    operation_id='list_organizations',
    tags=['Organizations'],
    summary='List Organizations',
    description='Retrieve organizations for the current user',
    responses={
        200: {
            'type': 'object',
            'properties': {
                'organizations': {'type': 'array', 'items': {'type': 'object'}},
                'status': {'type': 'string'}
            }
        }
    },
    methods=['GET']
)
@extend_schema(
    operation_id='create_organization',
    tags=['Organizations'],
    summary='Create Organization',
    description='Create a new organization',
    request=CreateOrganizationSerializer,
    responses={
        201: {
            'type': 'object',
            'properties': {
                'organization': {'type': 'object'},
                'status': {'type': 'string'}
            }
        },
        400: {
            'type': 'object',
            'properties': {
                'error': {'type': 'object'},
                'status': {'type': 'string'}
            }
        }
    },
    methods=['POST']
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def organizations_view(request):
    """List user's organizations or create new organization"""
    if request.method == 'GET':
        # Get organizations where user is a member
        organizations = Organization.objects.filter(
            Q(members__user=request.user) | Q(owner=request.user)
        ).distinct()
        
        serializer = OrganizationSerializer(organizations, many=True)
        return Response({
            'organizations': serializer.data,
            'status': 'success'
        })
    
    elif request.method == 'POST':
        serializer = CreateOrganizationSerializer(
            data=request.data, 
            context={'request': request}
        )
        if serializer.is_valid():
            organization = serializer.save()
            return Response({
                'organization': OrganizationSerializer(organization).data,
                'status': 'success'
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'error': serializer.errors,
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    operation_id='get_organization',
    tags=['Organizations'],
    summary='Get Organization',
    description='Retrieve a specific organization by ID',
    responses={
        200: {
            'type': 'object',
            'properties': {
                'organization': {'type': 'object'},
                'status': {'type': 'string'}
            }
        },
        403: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'status': {'type': 'string'}
            }
        },
        404: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'status': {'type': 'string'}
            }
        }
    },
    methods=['GET']
)
@extend_schema(
    operation_id='update_organization',
    tags=['Organizations'],
    summary='Update Organization',
    description='Update a specific organization',
    request=OrganizationSerializer,
    responses={
        200: {
            'type': 'object',
            'properties': {
                'organization': {'type': 'object'},
                'status': {'type': 'string'}
            }
        },
        400: {
            'type': 'object',
            'properties': {
                'error': {'type': 'object'},
                'status': {'type': 'string'}
            }
        },
        403: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'status': {'type': 'string'}
            }
        },
        404: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'status': {'type': 'string'}
            }
        }
    },
    methods=['PUT']
)
@extend_schema(
    operation_id='delete_organization',
    tags=['Organizations'],
    summary='Delete Organization',
    description='Delete a specific organization',
    responses={
        200: {
            'type': 'object',
            'properties': {
                'message': {'type': 'string'},
                'status': {'type': 'string'}
            }
        },
        403: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'status': {'type': 'string'}
            }
        },
        404: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'status': {'type': 'string'}
            }
        }
    },
    methods=['DELETE']
)
@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def organization_detail_view(request, org_id):
    """Get, update, or delete specific organization"""
    try:
        organization = Organization.objects.get(id=org_id)
        
        # Check if user has admin access
        if not organization.members.filter(user=request.user, role='admin').exists():
            return Response({
                'error': 'You do not have admin access to this organization',
                'status': 'error'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if request.method == 'GET':
            serializer = OrganizationSerializer(organization)
            return Response({
                'organization': serializer.data,
                'status': 'success'
            })
        
        elif request.method == 'PUT':
            serializer = OrganizationSerializer(organization, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    'organization': serializer.data,
                    'status': 'success'
                })
            else:
                return Response({
                    'error': serializer.errors,
                    'status': 'error'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        elif request.method == 'DELETE':
            # Only owner can delete organization
            if organization.owner != request.user:
                return Response({
                    'error': 'Only organization owner can delete the organization',
                    'status': 'error'
                }, status=status.HTTP_403_FORBIDDEN)
            
            organization.delete()
            return Response({
                'message': 'Organization deleted successfully',
                'status': 'success'
            })
    
    except Organization.DoesNotExist:
        return Response({
            'error': 'Organization not found',
            'status': 'error'
        }, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    operation_id='list_dashboard_templates',
    tags=['Dashboard Templates'],
    summary='List Dashboard Templates',
    description='Retrieve dashboard templates for the current user',
    responses={
        200: {
            'type': 'object',
            'properties': {
                'templates': {'type': 'array', 'items': {'type': 'object'}},
                'status': {'type': 'string'}
            }
        }
    },
    methods=['GET']
)
@extend_schema(
    operation_id='create_dashboard_template',
    tags=['Dashboard Templates'], 
    summary='Create Dashboard Template',
    description='Create a new dashboard template',
    request=CreateDashboardTemplateSerializer,
    responses={
        201: {
            'type': 'object',
            'properties': {
                'template': {'type': 'object'},
                'status': {'type': 'string'}
            }
        },
        400: {
            'type': 'object',
            'properties': {
                'error': {'type': 'object'},
                'status': {'type': 'string'}
            }
        }
    },
    methods=['POST']
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def dashboard_templates_view(request):
    """List user's dashboard templates or create new template"""
    if request.method == 'GET':
        # Get templates where user has access
        templates = DashboardTemplate.objects.filter(
            Q(organization__members__user=request.user) |
            Q(permissions__user=request.user) |
            Q(creator=request.user)
        ).distinct()
        
        serializer = DashboardTemplateSerializer(templates, many=True)
        return Response({
            'templates': serializer.data,
            'status': 'success'
        })
    
    elif request.method == 'POST':
        serializer = CreateDashboardTemplateSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            template = serializer.save()
            return Response({
                'template': DashboardTemplateSerializer(template).data,
                'status': 'success'
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'error': serializer.errors,
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    operation_id='get_dashboard_template',
    tags=['Dashboard Templates'],
    summary='Get Dashboard Template',
    description='Retrieve a specific dashboard template by UUID',
    responses={
        200: {
            'type': 'object',
            'properties': {
                'template': {'type': 'object'},
                'status': {'type': 'string'}
            }
        },
        403: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'status': {'type': 'string'}
            }
        },
        404: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'status': {'type': 'string'}
            }
        }
    },
    methods=['GET']
)
@extend_schema(
    operation_id='update_dashboard_template',
    tags=['Dashboard Templates'],
    summary='Update Dashboard Template',
    description='Update a specific dashboard template',
    request=DashboardTemplateSerializer,
    responses={
        200: {
            'type': 'object',
            'properties': {
                'template': {'type': 'object'},
                'status': {'type': 'string'}
            }
        },
        400: {
            'type': 'object',
            'properties': {
                'error': {'type': 'object'},
                'status': {'type': 'string'}
            }
        },
        403: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'status': {'type': 'string'}
            }
        },
        404: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'status': {'type': 'string'}
            }
        }
    },
    methods=['PUT']
)
@extend_schema(
    operation_id='delete_dashboard_template',
    tags=['Dashboard Templates'],
    summary='Delete Dashboard Template',
    description='Delete a specific dashboard template',
    responses={
        200: {
            'type': 'object',
            'properties': {
                'message': {'type': 'string'},
                'status': {'type': 'string'}
            }
        },
        403: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'status': {'type': 'string'}
            }
        },
        404: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'status': {'type': 'string'}
            }
        }
    },
    methods=['DELETE']
)
@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def dashboard_template_detail_view(request, template_uuid):
    """Get, update, or delete specific dashboard template"""
    try:
        # Fetch by UUID for shareable identifiers
        template = DashboardTemplate.objects.get(uuid=template_uuid)
        
        # Check user permissions
        has_admin_access = (
            template.creator == request.user or
            template.organization.members.filter(user=request.user, role='admin').exists() or
            template.permissions.filter(user=request.user, permission_type='admin').exists()
        )
        
        has_view_access = (
            has_admin_access or
            template.organization.members.filter(user=request.user).exists() or
            template.permissions.filter(user=request.user).exists()
        )
        
        if request.method == 'GET':
            if not has_view_access:
                return Response({
                    'error': 'You do not have access to this template',
                    'status': 'error'
                }, status=status.HTTP_403_FORBIDDEN)
            
            serializer = DashboardTemplateSerializer(template)
            return Response({
                'template': serializer.data,
                'status': 'success'
            })
        
        elif request.method in ['PUT', 'DELETE']:
            if not has_admin_access:
                return Response({
                    'error': 'You do not have admin access to this template',
                    'status': 'error'
                }, status=status.HTTP_403_FORBIDDEN)
            
            if request.method == 'PUT':
                serializer = DashboardTemplateSerializer(template, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    return Response({
                        'template': serializer.data,
                        'status': 'success'
                    })
                else:
                    return Response({
                        'error': serializer.errors,
                        'status': 'error'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            elif request.method == 'DELETE':
                template.delete()
                return Response({
                    'message': 'Template deleted successfully',
                    'status': 'success'
                })
    
    except DashboardTemplate.DoesNotExist:
        return Response({
            'error': 'Template not found',
            'status': 'error'
        }, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    operation_id='list_projects',
    tags=['Projects'],
    summary='List Projects',
    description='Retrieve projects for the current user',
    responses={
        200: {
            'type': 'object',
            'properties': {
                'projects': {'type': 'array', 'items': {'type': 'object'}},
                'status': {'type': 'string'}
            }
        }
    },
    methods=['GET']
)
@extend_schema(
    operation_id='create_project',
    tags=['Projects'],
    summary='Create Project',
    description='Create a new project',
    request=CreateProjectSerializer,
    responses={
        201: {
            'type': 'object',
            'properties': {
                'project': {'type': 'object'},
                'status': {'type': 'string'}
            }
        },
        400: {
            'type': 'object',
            'properties': {
                'error': {'type': 'object'},
                'status': {'type': 'string'}
            }
        }
    },
    methods=['POST']
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def projects_view(request):
    """List projects for user or create new project"""
    try:
        if request.method == 'GET':
            # Get projects for organizations where user is a member
            user_orgs = Organization.objects.filter(
                members__user=request.user
            ).values_list('id', flat=True)
            
            projects = Project.objects.filter(
                organization_id__in=user_orgs,
                is_active=True
            ).select_related('organization', 'creator')
            
            serializer = ProjectSerializer(projects, many=True)
            return Response({
                'projects': serializer.data,
                'status': 'success'
            })
        
        elif request.method == 'POST':
            serializer = CreateProjectSerializer(data=request.data, context={'request': request})
            if serializer.is_valid():
                project = serializer.save()
                return Response({
                    'project': ProjectSerializer(project).data,
                    'status': 'success'
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'error': serializer.errors,
                    'status': 'error'
                }, status=status.HTTP_400_BAD_REQUEST)
                
    except Exception as e:
        return Response({
            'error': 'Failed to process projects request',
            'status': 'error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    operation_id='get_project',
    tags=['Projects'],
    summary='Get Project',
    description='Retrieve a specific project by UUID',
    responses={
        200: {
            'type': 'object',
            'properties': {
                'project': {'type': 'object'},
                'status': {'type': 'string'}
            }
        },
        403: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'status': {'type': 'string'}
            }
        },
        404: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'status': {'type': 'string'}
            }
        }
    },
    methods=['GET']
)
@extend_schema(
    operation_id='update_project',
    tags=['Projects'],
    summary='Update Project',
    description='Update a specific project',
    request=ProjectSerializer,
    responses={
        200: {
            'type': 'object',
            'properties': {
                'project': {'type': 'object'},
                'status': {'type': 'string'}
            }
        },
        400: {
            'type': 'object',
            'properties': {
                'error': {'type': 'object'},
                'status': {'type': 'string'}
            }
        },
        403: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'status': {'type': 'string'}
            }
        },
        404: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'status': {'type': 'string'}
            }
        }
    },
    methods=['PUT']
)
@extend_schema(
    operation_id='delete_project',
    tags=['Projects'],
    summary='Delete Project',
    description='Delete a specific project',
    responses={
        200: {
            'type': 'object',
            'properties': {
                'message': {'type': 'string'},
                'status': {'type': 'string'}
            }
        },
        403: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'status': {'type': 'string'}
            }
        },
        404: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
                'status': {'type': 'string'}
            }
        }
    },
    methods=['DELETE']
)
@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def project_detail_view(request, project_uuid):
    """Get, update, or delete a specific project"""
    try:
        project = Project.objects.select_related('organization', 'creator').get(
            uuid=project_uuid,
            organization__members__user=request.user
        )
        
        if request.method == 'GET':
            serializer = ProjectSerializer(project)
            return Response({
                'project': serializer.data,
                'status': 'success'
            })
        
        elif request.method == 'PUT':
            # Check if user has admin access
            if not project.organization.members.filter(user=request.user, role='admin').exists():
                return Response({
                    'error': 'Admin access required to update projects',
                    'status': 'error'
                }, status=status.HTTP_403_FORBIDDEN)
            
            serializer = ProjectSerializer(project, data=request.data, partial=True)
            if serializer.is_valid():
                project = serializer.save()
                return Response({
                    'project': ProjectSerializer(project).data,
                    'status': 'success'
                })
            else:
                return Response({
                    'error': serializer.errors,
                    'status': 'error'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        elif request.method == 'DELETE':
            # Check if user has admin access
            if not project.organization.members.filter(user=request.user, role='admin').exists():
                return Response({
                    'error': 'Admin access required to delete projects',
                    'status': 'error'
                }, status=status.HTTP_403_FORBIDDEN)
            
            project.delete()
            return Response({
                'message': 'Project deleted successfully',
                'status': 'success'
            })
            
    except Project.DoesNotExist:
        return Response({
            'error': 'Project not found',
            'status': 'error'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'error': 'Failed to process project request',
            'status': 'error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
