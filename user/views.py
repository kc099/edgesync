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
@csrf_exempt
def login_view(request):
    """Secure login endpoint that handles encrypted data"""
    try:
        data = json.loads(request.body) if hasattr(request, 'body') else request.data
        
        # Check if data is encrypted
        if 'key' in data and 'iv' in data:
            try:
                # Decrypt the form data
                decrypted_data = encryption_manager.decrypt_form_data(data)
                email = decrypted_data.get('email')
                password = decrypted_data.get('password')
            except Exception as decrypt_error:
                # Fallback to plain data if decryption fails
                print(f"Decryption failed, using plain data: {decrypt_error}")
                email = data.get('data', {}).get('email')
                password = data.get('data', {}).get('password')
        else:
            # Plain data (for development/testing)
            email = data.get('email')
            password = data.get('password')
        
        if not email or not password:
            return Response({
                'error': 'Email and password are required',
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create serializer with decrypted/plain data
        serializer_data = {'email': email, 'password': password}
        serializer = LoginSerializer(data=serializer_data)
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
            tokens = get_tokens_for_user(user)
            
            return Response({
                'token': tokens['access'],
                'refresh': tokens['refresh'],
                'user': UserSerializer(user).data,
                'status': 'success'
            })
        else:
            return Response({
                'error': serializer.errors,
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except json.JSONDecodeError:
        return Response({
            'error': 'Invalid JSON data',
            'status': 'error'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'error': str(e),
            'status': 'error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def signup_view(request):
    """Secure signup endpoint that handles encrypted data"""
    try:
        data = json.loads(request.body) if hasattr(request, 'body') else request.data
        
        # Check if data is encrypted
        if 'key' in data and 'iv' in data:
            try:
                # Decrypt the form data
                decrypted_data = encryption_manager.decrypt_form_data(data)
            except Exception as decrypt_error:
                # Fallback to plain data if decryption fails
                print(f"Decryption failed, using plain data: {decrypt_error}")
                decrypted_data = data.get('data', {})
        else:
            # Plain data (for development/testing)
            decrypted_data = data
        
        # Validate required fields
        required_fields = ['username', 'email', 'password']
        missing_fields = [field for field in required_fields if not decrypted_data.get(field)]
        
        if missing_fields:
            return Response({
                'error': f'Missing required fields: {", ".join(missing_fields)}',
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Add password confirmation if not provided
        if 'password_confirm' not in decrypted_data:
            decrypted_data['password_confirm'] = decrypted_data['password']
        
        serializer = SignupSerializer(data=decrypted_data)
        
        if serializer.is_valid():
            user = serializer.save()
            tokens = get_tokens_for_user(user)
            
            return Response({
                'token': tokens['access'],
                'refresh': tokens['refresh'],
                'user': UserSerializer(user).data,
                'status': 'success'
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'error': serializer.errors,
                'status': 'error'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except json.JSONDecodeError:
        return Response({
            'error': 'Invalid JSON data',
            'status': 'error'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'error': str(e),
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
