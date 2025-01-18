from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import datetime
from django.core.validators import RegexValidator
from django.utils.text import slugify

class CustomUser(AbstractUser):
    """Custom user model extending Django's AbstractUser"""
    phone_number = models.CharField(max_length=13, blank=True, validators=[RegexValidator(r'^\+?\d{9,12}$', 'Enter a valid phone number.')])

class Customer(models.Model):
    """Customer model for storing customer-specific information"""
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='customer_profile')
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Customer: {self.user.username}"

class Vendor(models.Model):
    """Vendor model for storing vendor-specific information"""
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='vendor_profile')
    company_name = models.CharField(max_length=100)
    business_address = models.TextField()
    tax_id = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Vendor: {self.company_name}"

class ProductCategory(models.Model):
    """Model for managing product categories"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Product Categories"
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
        ]

        def __str__(self):
            return self.name

class Product(models.Model):
    """Product model for storing product information"""
    category = models.ForeignKey(ProductCategory, on_delete=models.PROTECT, related_name='products')
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='products')
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    sku = models.CharField(max_length=50, unique=True)
    image = models.ImageField(upload_to='product-images/', blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.vendor}-{self.name})")
        super().save(*args, **kwargs)

    class Meta:
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['category']),
            models.Index(fields=['vendor']),
        ]

    def __str__(self):
        return f"{self.name} - {self.sku}"


class Payment(models.Model):
    """Payment model for storing payment information"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded')
    ]


    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    transaction_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment #{self.id} - ${self.amount} ({self.status})"

from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
from django.db.models import Sum
from datetime import datetime

class Order(models.Model):
    """
    Order model for storing order information and managing payment status.
    Handles automatic tracking number generation and payment processing.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('SHIPPED', 'Shipped'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled')
    ]

    PAYMENT_STATUS_CHOICES = [
        ('UNPAID', 'Unpaid'),
        ('PARTIALLY_PAID', 'Partially Paid'),
        ('PAID', 'Paid'),
        ('REFUNDED', 'Refunded')
    ]

    # Core fields
    customer = models.ForeignKey(
        'Customer',
        on_delete=models.PROTECT,
        related_name='orders'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    items = models.ManyToManyField(
        'Product',
        through='OrderItem',
        related_name='orders'
    )
    payment = models.ManyToManyField(
        'Payment',
        related_name='orders',  # Changed from 'order' for consistency
        blank=True
    )

    # Status fields
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True  # Replaced manual index creation
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='UNPAID',
        db_index=True
    )

    # Payment tracking
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    # Shipping information
    shipping_address = models.TextField()
    tracking_number = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True,
        db_index=True
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']  # Default ordering
        indexes = [
            models.Index(fields=['customer', 'created_at']),  # Composite index for common queries
        ]

    @property
    def remaining_balance(self):
        """Calculate remaining balance to be paid."""
        return max(self.amount - self.amount_paid, Decimal('0.00'))

    @property
    def is_fully_paid(self):
        """Check if order is fully paid."""
        return self.amount_paid >= self.amount

    @staticmethod
    def generate_tracking_number(order_id):
        """Generate tracking number for an order."""
        prefix = 'SNBL'
        date = datetime.now().strftime('%Y%m%d')
        return f"{prefix}{date}-{order_id:06d}"

    def update_payment_status(self):
        """Update payment status based on amount paid."""
        if self.amount_paid >= self.amount:
            self.payment_status = 'PAID'
        elif self.amount_paid > 0:
            self.payment_status = 'PARTIALLY_PAID'
        else:
            self.payment_status = 'UNPAID'
        self.save()

    def add_payment(self, payment):
        """
        Add payment to order and update payment status.

        Args:
            payment: Payment object to be added
        """
        self.payment.add(payment)
        self.amount_paid = self.payment.aggregate(
            total=Sum('amount'))['total'] or Decimal('0.00')
        self.update_payment_status()

        # Generate tracking number if fully paid
        if self.is_fully_paid and not self.tracking_number:
            self.tracking_number = self.generate_tracking_number(self.id)
            self.save()

    def save(self, *args, **kwargs):
        """Override save to handle tracking number generation."""
        is_new = not self.pk

        if is_new:
            super().save(*args, **kwargs)
            self.tracking_number = self.generate_tracking_number(self.id)
            super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.id} - ${self.amount} - {self.get_status_display()}"

class OrderItem(models.Model):
    """Model for storing individual items within an order"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='order_items')
    quantity = models.PositiveIntegerField()
    price_at_time = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ['order', 'product']

    def __str__(self):
        return f"{self.quantity}x {self.product.name} in Order #{self.order.id}"
