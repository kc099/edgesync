"""
OAuth Account Handlers for merging accounts
"""
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages
from django.contrib.auth import get_user_model

User = get_user_model()

class MergingSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter to handle account merging between email-based accounts
    and social accounts
    """
    def pre_social_login(self, request, sociallogin):
        """
        Invoked just after a user successfully logs in using a social account,
        but before the login is actually processed.
        """
        # Check if this social account is already connected to a user
        if sociallogin.is_existing:
            return

        # Get the email from the social account
        email = sociallogin.account.extra_data.get('email', None)
        if not email:
            return
            
        # Check if a user with this email already exists in our database
        try:
            existing_user = User.objects.get(email=email)
            
            # Connect the social account to the existing user
            sociallogin.connect(request, existing_user)
            
            # Add a session message
            messages.success(
                request,
                f"Your {sociallogin.account.provider.capitalize()} account has been connected to your existing account."
            )
        except User.DoesNotExist:
            # No existing user with this email, so let the standard flow continue
            pass

    def populate_user(self, request, sociallogin, data):
        """
        Hook to populate standard user fields from social login data.
        """
        user = super().populate_user(request, sociallogin, data)
        if not user.username and user.email:
            user.username = user.email.split('@')[0]
        
        # Get profile info if available
        if sociallogin.account.provider == 'google':
            user_data = sociallogin.account.extra_data
            if 'name' in user_data:
                user.name = user_data.get('name', '')
            if 'given_name' in user_data:
                user.first_name = user_data.get('given_name', '')
            if 'family_name' in user_data:
                user.last_name = user_data.get('family_name', '')
            if 'picture' in user_data:
                user.photo_url = user_data.get('picture', '')
                
        return user 