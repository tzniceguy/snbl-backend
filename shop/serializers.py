from rest_framework import serializers
from django.contrib.auth import  authenticate
from .models import Customer, Vendor, Product, CustomUser,Order,Payment,OrderItem, ProductCategory



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
        fields = ('id', 'amount', 'payment_method', 'status', 'transaction_id',
                 'created_at', 'updated_at')
        read_only_fields = ('status', 'transaction_id', 'created_at', 'updated_at')


class OrderItemSerializer(serializers.ModelSerializer):
    #Serializer for order items with product details
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        required=True,
        allow_null=False,
        error_messages={
            'required': 'Product is required.',
            'null': 'Product cannot be null.',
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
    quantity = serializers.IntegerField(
        min_value=1,
        error_messages={
            'min_value': 'Quantity must be at least 1.',
            'required': 'Quantity is required.'
        }
    )

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
        read_only_fields = ['subtotal']

    def validate_product(self, value):
        #Additional validation for product
        if not isinstance(value, Product):
            raise serializers.ValidationError("Invalid product ID")
        return value

    def validate_quantity(self, value):
        #Validate quantity is positive
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value

class OrderSerializer(serializers.ModelSerializer):
    """
    Main serializer for Order model with nested relationships
    """
    items = OrderItemSerializer(source='order_items', many=True,required=True,error_messages={'required': 'At least one item is required.'})
    customer_name = serializers.CharField(source='customer.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(
        source='get_payment_status_display',
        read_only=True
    )

    class Meta:
        model = Order
        fields = [
            'id',
            'customer',
            'customer_name',
            'amount',
            'items',
            'status',
            'status_display',
            'payment_status',
            'payment_status_display',
            'amount_paid',
            'shipping_address',
            'tracking_number',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'customer',
            'amount_paid',
            'payment_status',
            'tracking_number',
            'created_at',
            'updated_at'
        ]

    def validate_items(self, value):
        """Validate that items are provided and valid"""
        if not value:
            raise serializers.ValidationError("At least one item is required")

        # Validate each item has valid product and quantity
        for item in value:
            if not item.get('product'):
                raise serializers.ValidationError("Product is required for each item")
            if not item.get('quantity'):
                raise serializers.ValidationError("Quantity is required for each item")
        return value

    def create(self, validated_data):
        """Create order with nested items"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required")

        items_data = validated_data.pop('orderitem_set', [])

        # Calculate total amount from items
        total_amount = sum(
            item['product'].price * item['quantity']
            for item in items_data
        )

        try:
            customer = request.user.customer
            validated_data['customer'] = customer
        except Customer.DoesNotExist:
            raise serializers.ValidationError("Customer profile not found")

        validated_data['amount'] = total_amount
        order = Order.objects.create(**validated_data)

        # Create order items
        for item_data in items_data:
            OrderItem.objects.create(
                order=order,
                product=item_data['product'],
                quantity=item_data['quantity']
            )

        return order

    def to_internal_value(self, data):
        """
        Additional preprocessing of input data to handle empty strings
        """
        # Convert empty strings to None for proper validation
        if isinstance(data, dict):
            for key, value in data.items():
                if value == '':
                    data[key] = None
        return super().to_internal_value(data)

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
