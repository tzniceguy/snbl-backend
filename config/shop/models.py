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

class Order(models.Model):
    """Order model for storing order information"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('SHIPPED', 'Shipped'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled')
    ]

    PAYMENT_STATUS_CHOICES =[
        ('UNPAID', 'Unpaid'),
        ('PARTIALLY_PAID', 'Partially Paid'),
        ('PAID', 'Paid'),
        ('REFUNDED', 'Refunded')
    ]

    '''function to auto generate tracking number for an order'''
    @staticmethod
    def generate_tracking_number(id):
        prefix = 'SNBL'
        date = datetime.now().strftime('%Y%m%d') #format date as YYYYMMDD
        return f"{prefix}{date}-{id:06d}"

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='orders')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    items = models.ManyToManyField(Product, through='OrderItem', related_name='orders')
    payment = models.ManyToManyField(Payment, related_name='order', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='UNPAID')
    amount_paid=models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_address = models.TextField()
    tracking_number = models.CharField(max_length=30, null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['customer']),
            models.Index(fields=['status']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['tracking_number']),
        ]

    def updatePaymentStatus(self):
        """update payment status based on amount paid"""
        total_paid = self.amount_paid
        if total_paid >= self.amount:
            self.payment_status = 'PAID'
        elif total_paid > 0:
            self.payment_status = 'PARTIALLY_PAID'
        else:
            self.payment_status = 'UNPAID'

    def addPayment(self, payment):
        """Add payment to order and update payment status"""
        self.payment.add(payment)
        self.amount_paid += payment.amount
        self.update_payment_status()

        if self.payment_status == 'PAID' and not self.tracking_number:
            self.tracking_number = self.generate_tracking_number(self.id)
            self.save()

    def save(self, *args, **kwargs):
            """Override save to generate tracking number if not set."""
            if not self.tracking_number and not self.id:
                # Save the instance and get id
                self.tracking_number = self.generate_tracking_number(self.id)
                super().save(*args, **kwargs)
            else:
                #normal save for updates
                super().save(*args, **kwargs)


    def __str__(self):
        return f"Order #{self.id} - ${self.amount}"

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
