from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.validators import RegexValidator

class User(AbstractUser):
    """Custom user model extending Django's AbstractUser"""
    # Add related_name to avoid clash with auth.User
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_set',
        blank=True,
        verbose_name='groups',
        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_user_set',
        blank=True,
        verbose_name='user permissions',
        help_text='Specific permissions for this user.',
    )
    
    phone_number = models.CharField(max_length=13, blank=True, validators=[RegexValidator(r'^\+?\d{9,12}$', 'Enter a valid phone number.')])
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

class Customer(models.Model):
    """Customer model for storing customer-specific information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    shipping_address = models.TextField(blank=True)
    billing_address = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Customer: {self.user.username}"

class Vendor(models.Model):
    """Vendor model for storing vendor-specific information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='vendor_profile')
    company_name = models.CharField(max_length=100)
    business_address = models.TextField()
    tax_id = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Vendor: {self.company_name}"

class Product(models.Model):
    """Product model for storing product information"""
    CATEGORY_CHOICES = [
        ('ELECTRONICS', 'Electronics'),
        ('CLOTHING', 'Clothing'),
        ('BOOKS', 'Books'),
        ('HOME', 'Home & Garden'),
        ('OTHER', 'Other'),
    ]

    name = models.CharField(max_length=200)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='products')
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='OTHER')
    stock = models.IntegerField(default=0)
    sku = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['category']),
            models.Index(fields=['vendor']),
        ]

    def __str__(self):
        return f"{self.name} - {self.sku}"