from django.contrib.auth.backends import BaseBackend
from .models import CustomUser

class PhoneBackend(BaseBackend):
    """
    Custom authentication backend to allow users to log in using phone number
    """
    def authenticate(self, request, phone_number=None, password=None, **kwargs):
        """
        Authenticate a user based on phone number and password.

        Args:
            request: The HTTP request
            phone_number: User's phone number
            password: User's password
            **kwargs: Additional arguments

        Returns:
            CustomUser object if authentication successful, None otherwise
        """
        try:
            user = CustomUser.objects.get(phone_number=phone_number)
            if user.check_password(password):
                return user
            return None
        except CustomUser.DoesNotExist:
            return None

    def get_user(self, user_id):
        """
        Retrieve a user by their primary key (ID)

        Args:
            user_id: The primary key of the user

        Returns:
            CustomUser object if found, None otherwise
        """
        try:
            return CustomUser.objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            return None
