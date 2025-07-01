from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from google.oauth2 import id_token
from google.auth.transport import requests
from django.contrib.auth import get_user_model
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
import os
from .models import User

@api_view(['POST'])
@permission_classes([AllowAny])
def google_login(request):
    """
    Google OAuth login endpoint that accepts Google JWT credential
    """
    try:
        credential = request.data.get('access_token')
        if not credential:
            return Response(
                {'error': 'access_token is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify the Google JWT token
        idinfo = id_token.verify_oauth2_token(
            credential, 
            requests.Request(), 
            os.getenv('GOOGLE_CLIENT_ID')
        )

        # Extract user information
        google_user_id = idinfo['sub']
        email = idinfo['email']
        first_name = idinfo.get('given_name', '')
        last_name = idinfo.get('family_name', '')
        picture = idinfo.get('picture', '')

        # Check if user exists
        try:
            user = User.objects.get(email=email)
            created = False
        except User.DoesNotExist:
            # Create new user
            user = User.objects.create_user(
                username=email,  # Use email as username or generate a unique username
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_active=True
            )
            # You can save additional Google data here
            created = True

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token

        return Response({
            'user': {
                'id': user.pk,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
            'access_token': str(access_token),
            'refresh_token': str(refresh),
            'created': created
        }, status=status.HTTP_200_OK)

    except ValueError as e:
        return Response(
            {'error': 'Invalid Google token'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': 'Authentication failed'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )