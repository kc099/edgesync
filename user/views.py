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
            
            # Count items before deletion
            projects_count = organization.projects.count()
            dashboards_count = organization.dashboard_templates.count()
            devices_count = organization.devices.count()
            
            # Set related projects to inactive instead of deleting them
            organization.projects.update(status='inactive', is_active=False)
            
            # Set related dashboard templates to inactive
            organization.dashboard_templates.update(is_active=False)
            
            # For devices, we can't just set them to inactive because they have CASCADE
            # relation to organization. For now, we'll let them be deleted with the organization.
            # In a real production system, you might want to transfer devices to another organization
            # or change the CASCADE to SET_NULL/SET_DEFAULT behavior
            
            # Now delete the organization (members and devices will be cascade deleted)
            # Note: Projects and dashboards are preserved but inactive
            organization.delete()
            
            message = f'Organization deleted successfully. {projects_count} projects and {dashboards_count} dashboards have been set to inactive but preserved. {devices_count} devices were deleted with the organization.'
            
            return Response({
                'message': message,
                'status': 'success'
            })
    
    except Organization.DoesNotExist:
        return Response({
            'error': 'Organization not found',
            'status': 'error'
        }, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    operation_id='list_organization_members',
    tags=['Organizations'],
    summary='List Organization Members',
    description='Retrieve members of a specific organization',
    responses={
        200: {
            'type': 'object',
            'properties': {
                'members': {'type': 'array', 'items': {'type': 'object'}},
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
    operation_id='add_organization_member',
    tags=['Organizations'],
    summary='Add Organization Member',
    description='Add a new member to the organization',
    request={
        'type': 'object',
        'properties': {
            'email': {'type': 'string', 'description': 'User email to add'},
            'role': {'type': 'string', 'description': 'Member role (admin/user)', 'enum': ['admin', 'user']}
        },
        'required': ['email', 'role']
    },
    responses={
        201: {
            'type': 'object',
            'properties': {
                'member': {'type': 'object'},
                'status': {'type': 'string'}
            }
        },
        400: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'},
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
    methods=['POST']
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def organization_members_view(request, org_id):
    """List organization members or add new member"""
    try:
        organization = Organization.objects.get(id=org_id)
        
        # Check if user has admin access
        if not organization.members.filter(user=request.user, role='admin').exists() and organization.owner != request.user:
            return Response({
                'error': 'You do not have admin access to this organization',
                'status': 'error'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if request.method == 'GET':
            # Get all members including the owner
            members = list(organization.members.all())
            
            # Add owner as a special member entry if not already in members
            owner_is_member = any(member.user.id == organization.owner.id for member in members)
            if not owner_is_member:
                # Create a temporary member object for the owner
                owner_member = OrganizationMember(
                    organization=organization,
                    user=organization.owner,
                    role='admin',
                    joined_at=organization.created_at
                )
                members.insert(0, owner_member)
            
            serializer = OrganizationMemberSerializer(members, many=True)
            return Response({
                'members': serializer.data,
                'status': 'success'
            })
        
        elif request.method == 'POST':
            email = request.data.get('email')
            role = request.data.get('role', 'user')
            
            if not email:
                return Response({
                    'error': 'Email is required',
                    'status': 'error'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                user_to_add = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({
                    'error': 'User with this email does not exist',
                    'status': 'error'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if user is already a member
            if organization.members.filter(user=user_to_add).exists():
                return Response({
                    'error': 'User is already a member of this organization',
                    'status': 'error'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if trying to add the owner
            if user_to_add == organization.owner:
                return Response({
                    'error': 'User is already the owner of this organization',
                    'status': 'error'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create the membership
            member = OrganizationMember.objects.create(
                organization=organization,
                user=user_to_add,
                role=role,
                invited_by=request.user
            )
            
            serializer = OrganizationMemberSerializer(member)
            return Response({
                'member': serializer.data,
                'status': 'success'
            }, status=status.HTTP_201_CREATED)
    
    except Organization.DoesNotExist:
        return Response({
            'error': 'Organization not found',
            'status': 'error'
        }, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    operation_id='remove_organization_member',
    tags=['Organizations'],
    summary='Remove Organization Member',
    description='Remove a member from the organization',
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
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def organization_member_detail_view(request, org_id, member_id):
    """Remove organization member"""
    try:
        organization = Organization.objects.get(id=org_id)
        member = OrganizationMember.objects.get(id=member_id, organization=organization)
        
        # Check if user has admin access
        if not organization.members.filter(user=request.user, role='admin').exists() and organization.owner != request.user:
            return Response({
                'error': 'You do not have admin access to this organization',
                'status': 'error'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Cannot remove the owner
        if member.user == organization.owner:
            return Response({
                'error': 'Cannot remove the organization owner',
                'status': 'error'
            }, status=status.HTTP_403_FORBIDDEN)
        
        member.delete()
        return Response({
            'message': 'Member removed successfully',
            'status': 'success'
        })
    
    except Organization.DoesNotExist:
        return Response({
            'error': 'Organization not found',
            'status': 'error'
        }, status=status.HTTP_404_NOT_FOUND)
    
    except OrganizationMember.DoesNotExist:
        return Response({
            'error': 'Member not found',
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
        
        # Filter by project if provided
        project_id = request.GET.get('project')
        if project_id:
            templates = templates.filter(project__uuid=project_id)
        
        serializer = DashboardTemplateSerializer(templates, many=True)
        return Response({
            'results': serializer.data,  # Changed from 'templates' to 'results' to match frontend expectation
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
    operation_id='get_dashboard_widget_data',
    tags=['Dashboard Templates'],
    summary='Get Dashboard Widget Data',
    description='Get data for a specific widget in a dashboard template',
    parameters=[
        OpenApiParameter(
            name='template_uuid',
            type=OpenApiTypes.UUID,
            location=OpenApiParameter.PATH,
            description='Dashboard template UUID'
        ),
        OpenApiParameter(
            name='widget_id',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.PATH,
            description='Widget ID within the dashboard'
        )
    ],
    responses={
        200: {
            'type': 'object',
            'properties': {
                'widget_id': {'type': 'string'},
                'widget_type': {'type': 'string'},
                'data': {'type': 'object'},
                'meta': {'type': 'object'}
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
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_widget_data_view(request, template_uuid, widget_id):
    """Get data for a specific widget in a dashboard template"""
    try:
        # Get dashboard template
        template = DashboardTemplate.objects.get(uuid=template_uuid)
        
        # Check permissions
        has_view_access = (
            template.creator == request.user or
            template.organization.members.filter(user=request.user).exists() or
            template.permissions.filter(user=request.user).exists()
        )
        
        if not has_view_access:
            return Response({
                'error': 'You do not have access to this template',
                'status': 'error'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Find widget in dashboard template
        widget_config = None
        for widget in template.widgets or []:
            if widget.get('id') == widget_id:
                widget_config = widget
                break
        
        if not widget_config:
            return Response({
                'error': 'Widget not found in dashboard template',
                'status': 'error'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get data source configuration
        data_source = widget_config.get('dataSource', {})
        
        if data_source.get('type') == 'flow_node':
            return _get_flow_node_widget_data(data_source, widget_config)
        else:
            return Response({
                'error': f"Unsupported data source type: {data_source.get('type')}",
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except DashboardTemplate.DoesNotExist:
        return Response({
            'error': 'Dashboard template not found',
            'status': 'error'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'error': str(e),
            'status': 'error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _get_flow_node_widget_data(data_source, widget_config):
    """Get data for flow node data source (uses NodeExecution records)"""
    from flows.models import FlowDiagram, NodeExecution
    from django.utils import timezone
    from datetime import timedelta
    
    try:
        # Get flow and node data
        flow = FlowDiagram.objects.get(uuid=data_source['flowUuid'])
        node_id = data_source['nodeId']
        output_field = data_source.get('outputField', 'output')
        
        # Determine data range based on widget type
        widget_type = widget_config.get('type')
        
        if widget_type in ['time_series', 'bar_chart']:
            # Get historical data for charts
            hours = 24  # Last 24 hours
            since_time = timezone.now() - timedelta(hours=hours)
            
            outputs = (
                NodeExecution.objects.filter(
                    flow_execution__flow=flow,
                    node_id=node_id,
                    status='completed',
                    executed_at__gte=since_time
                ).order_by('executed_at')[:1000]
            )
            
            # Transform data for chart widgets
            chart_data = []
            for out in outputs:
                value = out.output_data.get(output_field)
                if value is not None:
                    chart_data.append({
                        'timestamp': out.executed_at.isoformat() if out.executed_at else None,
                        'value': value,
                        'label': out.executed_at.strftime('%H:%M') if out.executed_at else ''
                    })
            
            return Response({
                'widget_id': widget_config.get('id'),
                'widget_type': widget_type,
                'data': chart_data,
                'meta': {
                    'total_points': len(chart_data),
                    'time_range': f'{hours} hours',
                    'last_updated': timezone.now().isoformat()
                },
                'status': 'success'
            })
            
        elif widget_type in ['gauge', 'stat_panel']:
            # Get latest value for single-value widgets
            latest_output = (
                NodeExecution.objects.filter(
                    flow_execution__flow=flow,
                    node_id=node_id,
                    status='completed'
                ).order_by('-executed_at').first()
            )
            
            if not latest_output:
                return Response({
                    'widget_id': widget_config.get('id'),
                    'widget_type': widget_type,
                    'data': None,
                    'message': 'No data available',
                    'status': 'success'
                })
            
            value = latest_output.output_data.get(output_field)
            
            # Calculate trend for stat panel
            trend_data = None
            if widget_type == 'stat_panel':
                # Get previous value for trend calculation
                previous_output = (
                    NodeExecution.objects.filter(
                        flow_execution__flow=flow,
                        node_id=node_id,
                        status='completed',
                        executed_at__lt=latest_output.executed_at if latest_output else None
                    ).order_by('-executed_at').first()
                )
                
                if previous_output:
                    previous_value = previous_output.output_data.get(output_field)
                    if previous_value is not None and value is not None:
                        trend_data = {
                            'change': value - previous_value,
                            'percentage': ((value - previous_value) / previous_value * 100) if previous_value != 0 else 0,
                            'direction': 'up' if value > previous_value else 'down' if value < previous_value else 'stable'
                        }
            
            return Response({
                'widget_id': widget_config.get('id'),
                'widget_type': widget_type,
                'data': {
                    'value': value,
                    'timestamp': latest_output.executed_at.isoformat() if latest_output.executed_at else None,
                    'trend': trend_data
                },
                'meta': {
                    'last_updated': latest_output.executed_at.isoformat() if latest_output.executed_at else None
                },
                'status': 'success'
            })
            
        else:
            return Response({
                'error': f"Widget type '{widget_type}' not supported yet",
                'status': 'error'
            }, status=status.HTTP_501_NOT_IMPLEMENTED)
            
    except FlowDiagram.DoesNotExist:
        return Response({
            'error': 'Flow not found',
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
            
            # Before deleting the project, unassign all devices from this project
            # This prevents devices from being deleted with the project
            devices_count = project.devices.count()
            flows_count = project.flows.count()
            dashboards_count = project.dashboard_templates.count()
            
            # Unassign devices from the project (preserves the devices)
            project.devices.clear()
            
            # Now delete the project (flows and dashboards will be cascade deleted as intended)
            project.delete()
            
            message = f'Project deleted successfully. {devices_count} devices have been unassigned and preserved.'
            if flows_count > 0:
                message += f' {flows_count} flows were deleted.'
            if dashboards_count > 0:
                message += f' {dashboards_count} dashboards were deleted.'
            
            return Response({
                'message': message,
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

# ---------------------------------------------------------------------------
#  Widget samples endpoint (device widgets)
# ---------------------------------------------------------------------------


@extend_schema(
    operation_id='get_widget_samples',
    tags=['Dashboard Templates'],
    summary='Get Widget Samples',
    description='Return last N samples (<=50) for a widget that tracks a device variable',
    parameters=[
        {
            'name': 'template_uuid',
            'in': 'path',
            'type': 'string',
            'description': 'Dashboard template UUID'
        },
        {
            'name': 'widget_id',
            'in': 'path',
            'type': 'string',
            'description': 'Widget ID'
        }
    ],
    responses={
        200: {
            'type': 'object',
            'properties': {
                'data': {'type': 'array'},
                'widget_id': {'type': 'string'}
            }
        }
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def widget_samples_view(request, template_uuid, widget_id):
    from sensors.models import TrackedVariable, WidgetSample
    try:
        tv = TrackedVariable.objects.filter(widget_id=widget_id, dashboard_uuid=template_uuid).first()
        if not tv:
            return Response({'data': [], 'widget_id': widget_id})
        samples = WidgetSample.objects.filter(widget=tv).order_by('-timestamp')[:tv.max_samples]
        data = [
            {
                'timestamp': s.timestamp.isoformat(),
                'value': s.value,
                'unit': s.unit
            } for s in reversed(samples)  # oldest→newest
        ]
        return Response({'widget_id': widget_id, 'data': data})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
