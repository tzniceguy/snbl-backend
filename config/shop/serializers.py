from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Customer, Vendor, Product, User,Order,Payment,OrderItem


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 
                 'phone_number', 'address', 'created_at')
        read_only_fields = ('created_at',)
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        instance = super().create(validated_data)
        if password:
            instance.set_password(password)
            instance.save()
        return instance

class CustomerSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = Customer
        fields = ('id', 'user', 'shipping_address', 
                 'billing_address', 'created_at')
        read_only_fields = ['created_at']

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = User.objects.create(**user_data)
        customer = Customer.objects.create(user=user, **validated_data)
        return customer

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        for attr, value in user_data.items():
            setattr(instance.user, attr, value)
        instance.user.save()
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class VendorSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = Vendor
        fields = ('id', 'user', 'company_name', 'business_address', 
                 'tax_id', 'description', 'is_active','created_at')
        read_only_fields = ['created_at']

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = User.objects.create(**user_data)
        vendor = Vendor.objects.create(user=user, **validated_data)
        return vendor

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        for attr, value in user_data.items():
            setattr(instance.user, attr, value)
        instance.user.save()
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class ProductSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.company_name', read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ('id', 'name', 'vendor', 'vendor_name', 'description', 
                 'price', 'category', 'stock', 'sku', 
                 'image', 'image_url', 'created_at')
        read_only_fields = ('created_at',)

    def get_image_url(self, obj):
        if obj.image:
            return self.context['request'].build_absolute_uri(obj.image.url)
        return None

    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Stock cannot be negative.")
        return value

    def validate_price(self, value):
        if value <= 0:
            raise

# Nested serializers for detailed views
class ProductDetailSerializer(ProductSerializer):
    vendor = VendorSerializer(read_only=True)

class VendorDetailSerializer(VendorSerializer):
    products = ProductSerializer(many=True, read_only=True)

    class Meta(VendorSerializer.Meta):
        fields = VendorSerializer.Meta.fields + ('products',)

class CustomerDetailSerializer(CustomerSerializer):
    user = UserSerializer(read_only=True)

    class Meta(CustomerSerializer.Meta):
        fields = CustomerSerializer.Meta.fields


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    
    class Meta:
        model = OrderItem
        fields = ('id', 'product', 'product_name', 'quantity', 'price_at_time')
        read_only_fields = ('price_at_time',)

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ('id', 'amount', 'payment_method', 'status', 'transaction_id', 
                 'created_at', 'updated_at')
        read_only_fields = ('status', 'transaction_id', 'created_at', 'updated_at')

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(source='order_items', many=True, read_only=True)
    payment = PaymentSerializer(read_only=True)
    customer_name = serializers.CharField(source='customer.user.username', read_only=True)

    class Meta:
        model = Order
        fields = ('id', 'customer', 'customer_name', 'amount', 'items', 'payment',
                 'status', 'shipping_address', 'tracking_number', 'created_at')
        read_only_fields = ('amount', 'status', 'tracking_number', 'created_at')

    def create(self, validated_data):
        items_data = self.context.get('items', [])
        if not items_data:
            raise serializers.ValidationError({"items": "Order must contain at least one item."})

        # Calculate total amount
        total_amount = 0
        for item in items_data:
            product = Product.objects.get(pk=item['product'])
            if product.stock < item['quantity']:
                raise serializers.ValidationError(
                    f"Not enough stock for product {product.name}. Available: {product.stock}")
            total_amount += product.price * item['quantity']

        # Create order
        validated_data['amount'] = total_amount
        order = Order.objects.create(**validated_data)

        # Create order items
        for item in items_data:
            product = Product.objects.get(pk=item['product'])
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=item['quantity'],
                price_at_time=product.price
            )
            # Update stock
            product.stock -= item['quantity']
            product.save()

        return order

class OrderDetailSerializer(OrderSerializer):
    items = OrderItemSerializer(source='order_items', many=True)
    payment = PaymentSerializer()
    customer = CustomerSerializer()