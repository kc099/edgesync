from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json

from .serializers import LoginSerializer, SignupSerializer, UserSerializer
from .utils.encryption import encryption_manager
from .models import UserProfile


def get_tokens_for_user(user):
    """Generate JWT tokens for user"""
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


@api_view(['GET'])
@permission_classes([AllowAny])
def get_public_key(request):
    """Endpoint to provide RSA public key to frontend"""
    try:
        public_key = encryption_manager.get_public_key_pem()
        return Response({
            'public_key': public_key,
            'status': 'success'
        })
    except Exception as e:
        return Response({
            'error': str(e),
            'status': 'error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
                'error': 'Failed to decrypt authentication data',
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


@api_view(['POST'])
@permission_classes([AllowAny])  # Allow unauthenticated access for logout
def logout_view(request):
    """Logout user by blacklisting refresh token"""
    try:
        data = request.data
        refresh_token = data.get('refresh')
        
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
            
        return Response({
            'message': 'Successfully logged out',
            'status': 'success'
        })
    except Exception as e:
        return Response({
            'error': str(e),
            'status': 'error'
        }, status=status.HTTP_400_BAD_REQUEST)


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
