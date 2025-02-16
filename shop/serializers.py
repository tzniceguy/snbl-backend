from rest_framework import serializers
from django.contrib.auth import  authenticate
from .models import Customer, Vendor, Product, CustomUser,Order,Payment,OrderItem, ProductCategory
from django.db import transaction




class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('id', 'username', 'email', 'first_name', 'last_name',
                 'phone_number', 'date_joined')
        read_only_fields = ('date_joined',)
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
        fields = ('id', 'user', 'address', 'created_at')
        read_only_fields = ['created_at']

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = CustomUser.objects.create(**user_data)
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
                 'tax_id', 'description')


    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user = CustomUser.objects.create(**user_data)
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

class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ('id', 'name', 'description', 'created_at')
        read_only_fields = ('created_at',)

class ProductSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.company_name', read_only=True)
    image_url = serializers.SerializerMethodField()
    category = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Product
        fields = ('id', 'name','slug', 'vendor_name', 'description',
                 'price', 'category', 'stock', 'sku',
                 'image_url', 'created_at')
        lookup_field = ['id', 'slug']
        read_only_fields = ('created_at',)
        extra_kwargs = {
            'url': {'lookup_field': 'slug'}
        }



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
    pass

class VendorDetailSerializer(VendorSerializer):
    products = ProductSerializer(many=True, read_only=True)

    class Meta(VendorSerializer.Meta):
        fields = VendorSerializer.Meta.fields + ('products',)

class CustomerDetailSerializer(CustomerSerializer):
    user = UserSerializer(read_only=True)

    class Meta(CustomerSerializer.Meta):
        fields = CustomerSerializer.Meta.fields

class CustomerRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)
    user = UserSerializer()

    class Meta:
        model = Customer
        fields = ('id', 'user', 'address', 'created_at', 'password', 'password2')
        read_only_fields = ['created_at']

    def validate(self, data):
        # Ensure the two passwords match
        if data['password'] != data['password2']:
            raise serializers.ValidationError({'password': 'Passwords must match.'})
        return data

    def create(self, validated_data):
        # Extract password and address from validated data
        password = validated_data.pop('password')
        validated_data.pop('password2')
        address = validated_data.pop('address', '')

        # Extract user data from validated data
        user_data = validated_data.pop('user')

        # Create CustomUser instance
        user = CustomUser.objects.create_user(**user_data)
        user.set_password(password)
        user.save()

        # Create Customer instance linked to the user
        customer = Customer.objects.create(
            user=user,
            address=address
        )
        return customer

class CustomerLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

    def authenticate(self, request, username=None, password=None):
        try:
            user = authenticate(request, username=username, password=password)
            return user
        except:
            return None


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ('id', 'amount', 'payment_method', 'transaction_id',
                 'phone_number','status', 'order', 'created_at', 'updated_at')
        read_only_fields = ('id', 'status', 'created_at','transaction_id')

    def validate_phone_number(self, value):
            #remove any spaces or special characters
            cleaned_number = ''.join(filter(str.isdigit, value))

            if not cleaned_number.startswith('255'):
                raise serializers.ValidationError("Phone number must start with 255")

            if len(cleaned_number) != 12:
                raise serializers.ValidationError("Phone number must be 12 digits")
            return cleaned_number

    def validate_amount(self, value):
            if value <= 0:
                raise serializers.ValidationError("Amount must be greater than 0")
            return value

class PaymentResponseSerializer(serializers.ModelSerializer):
    azampay_response = serializers.DictField(read_only=True)

    class Meta:
        model = Payment
        fields = ['id', 'order', 'status', 'azampay_response']



class OrderItemSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        required=True,
        error_messages={
            'required': 'Product is required.',
            'does_not_exist': 'Product with this ID does not exist.'
        }
    )
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_price = serializers.DecimalField(
        source='product.price',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    quantity = serializers.IntegerField(min_value=1)
    subtotal = serializers.SerializerMethodField()  # Dynamically calculate subtotal

    class Meta:
        model = OrderItem
        fields = [
            'id',
            'product',
            'product_name',
            'product_price',
            'quantity',
            'subtotal'
        ]
        read_only_fields = ['id', 'product_name', 'product_price', 'subtotal']

    def get_subtotal(self, obj):
        # Calculate subtotal as quantity * product price
        return obj.quantity * obj.product.price

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(source='order_items', many=True, required=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'customer',
            'items',
            'amount',
            'shipping_address',
            'status',
            'payment_status',
            'amount_paid',
            'amount_remaining',
            'tracking_number',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'customer',
            'amount_paid',
            'amount_remaining',
            'payment_status',
            'tracking_number',
            'created_at',
            'updated_at'
        ]

    def create(self, validated_data):
        # Debug: Print the validated data
        print("Validated Data:", validated_data)

        # Extract items data from the payload
        items_data = validated_data.pop('order_items', [])
        if not items_data:
            raise serializers.ValidationError("No order items provided")

        # Get the authenticated user
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required")

        # Get the Customer profile associated with the user
        try:
            customer = request.user.customer
        except AttributeError:
            raise serializers.ValidationError("Customer profile not found")

        # Use a transaction to ensure atomicity
        with transaction.atomic():
            # Add the customer to the validated data
            validated_data['customer'] = customer

            # Create the order
            order = Order.objects.create(**validated_data)

            # Create order items and associate them with the order
            order_items = [OrderItem(order=order, **item) for item in items_data]
            OrderItem.objects.bulk_create(order_items)

        return order


class OrderListSerializer(OrderSerializer):
    """Simplified serializer for list views"""
    class Meta(OrderSerializer.Meta):
        fields = [
            'id',
            'customer_name',
            'amount',
            'status_display',
            'payment_status_display',
            'tracking_number',
            'created_at'
        ]
