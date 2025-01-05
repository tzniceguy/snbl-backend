from rest_framework import viewsets, filters, status
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from django.db.models import Prefetch
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from .models import Customer, Vendor, Product, User, Order, Payment
from .serializers import (
    UserSerializer, CustomerSerializer, VendorSerializer, ProductSerializer,
    CustomerDetailSerializer, VendorDetailSerializer, ProductDetailSerializer,
    OrderSerializer, OrderDetailSerializer, PaymentSerializer
)

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [filters.SearchFilter]
    search_fields = ['username', 'email', 'first_name', 'last_name']

    def perform_destroy(self, instance):
        if instance.is_superuser:
            raise PermissionDenied("Superusers cannot be deleted")
        instance.delete()

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.select_related('user')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['user__username', 'user__email', 'shipping_address']

    def get_serializer_class(self):
        if self.action in ['retrieve', 'me']:
            return CustomerDetailSerializer
        return CustomerSerializer

    def get_permissions(self):
        if self.action in ['create', 'list']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['GET'], permission_classes=[IsAuthenticated])
    def me(self, request):
        customer = get_object_or_404(self.get_queryset(), user=request.user)
        serializer = self.get_serializer(customer)
        return Response(serializer.data)

    def perform_update(self, serializer):
        if not self.request.user.is_staff and serializer.instance.user != self.request.user:
            raise PermissionDenied("You can only update your own profile")
        serializer.save()

class VendorViewSet(viewsets.ModelViewSet):
    queryset = Vendor.objects.select_related('user')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['company_name', 'user__email', 'description']
    filterset_fields = ['is_active']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return VendorDetailSerializer
        return VendorSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['GET'], permission_classes=[IsAuthenticated])
    def me(self, request):
        vendor = get_object_or_404(self.get_queryset(), user=request.user)
        serializer = self.get_serializer(vendor)
        return Response(serializer.data)

    @action(detail=True, methods=['GET'])
    def products(self, request, pk=None):
        vendor = self.get_object()
        products = vendor.products.select_related('vendor').all()
        page = self.paginate_queryset(products)
        serializer = ProductSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def perform_update(self, serializer):
        if not self.request.user.is_staff and serializer.instance.user != self.request.user:
            raise PermissionDenied("You can only update your own vendor profile")
        serializer.save()

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related('vendor').prefetch_related('order_items')
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'sku', 'vendor__company_name']
    filterset_fields = {
        'category': ['exact'],
        'vendor': ['exact'],
        'price': ['gte', 'lte'],
        'stock': ['gte', 'lte'],
    }
    ordering_fields = ['price', 'created_at', 'name', 'stock']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProductDetailSerializer
        return ProductSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [AllowAny]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        vendor = get_object_or_404(Vendor, user=self.request.user)
        if not vendor.is_active:
            raise PermissionDenied("Inactive vendors cannot create products")
        serializer.save(vendor=vendor)

    def perform_update(self, serializer):
        if not self.request.user.is_staff and serializer.instance.vendor.user != self.request.user:
            raise PermissionDenied("You can only update your own products")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.order_items.exists():
            raise ValidationError("Cannot delete product with existing orders")
        instance.delete()

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.select_related(
        'customer__user',
        'payment'
    ).prefetch_related(
        Prefetch('items', queryset=Product.objects.select_related('vendor'))
    )
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        'status': ['exact'],
        'customer': ['exact'],
        'created_at': ['gte', 'lte'],
        'amount': ['gte', 'lte'],
    }
    search_fields = ['id', 'tracking_number']
    ordering_fields = ['created_at', 'amount', 'status']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return OrderDetailSerializer
        return OrderSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_staff:
            return queryset
        
        if hasattr(user, 'vendor_profile'):
            # Vendors can see orders containing their products
            return queryset.filter(items__vendor__user=user).distinct()
        
        return queryset.filter(customer__user=user)

    def perform_create(self, serializer):
        customer = get_object_or_404(Customer, user=self.request.user)
        serializer.save(customer=customer)

    @action(detail=True, methods=['POST'])
    def process_payment(self, request, pk=None):
        order = self.get_object()
        payment_method = request.data.get('payment_method')
        
        if order.status != 'PENDING':
            raise ValidationError("Only pending orders can be processed for payment")

        if not payment_method:
            raise ValidationError("Payment method is required")

        if order.payment:
            raise ValidationError("Order has already been paid")

        # Verify stock availability
        for item in order.order_items.all():
            if item.quantity > item.product.stock:
                raise ValidationError(f"Insufficient stock for product: {item.product.name}")
            
            # Update stock
            item.product.stock -= item.quantity
            item.product.save()

        try:
            # Create payment (In production, integrate with payment gateway)
            payment = Payment.objects.create(
                amount=order.amount,
                payment_method=payment_method,
                status='COMPLETED',
                transaction_id=f"TRANS_{order.id}_{timezone.now().timestamp()}"
            )
            
            # Update order
            order.payment = payment
            order.status = 'PROCESSING'
            order.save()

            return Response(OrderDetailSerializer(order).data)
        
        except Exception as e:
            # Rollback stock updates in case of payment failure
            for item in order.order_items.all():
                item.product.stock += item.quantity
                item.product.save()
            raise ValidationError(f"Payment processing failed: {str(e)}")

class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = {
        'status': ['exact'],
        'payment_method': ['exact'],
        'created_at': ['gte', 'lte'],
        'amount': ['gte', 'lte'],
    }
    ordering_fields = ['created_at', 'amount', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        queryset = Payment.objects.select_related('order__customer__user')
        
        if user.is_staff:
            return queryset
            
        if hasattr(user, 'vendor_profile'):
            return queryset.filter(order__items__vendor__user=user).distinct()
            
        return queryset.filter(order__customer__user=user)