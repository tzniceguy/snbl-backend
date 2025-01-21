from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets, filters, status, generics
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import login
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Customer, Vendor, Product, CustomUser as User, Order, Payment
from .serializers import (
    UserSerializer, CustomerSerializer, VendorSerializer, ProductSerializer,
    CustomerDetailSerializer, VendorDetailSerializer, ProductDetailSerializer,
    OrderSerializer, PaymentSerializer , CustomerRegisterSerializer, CustomerLoginSerializer,PaymentResponseSerializer
)
import uuid
from azampay import Azampay
from django.conf import settings


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

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return VendorDetailSerializer
        elif self.action == 'create':
            return VendorCreateSerializer
        return VendorSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def create(self, request, *args, **kwargs):
            # Check if user already has a vendor profile
            if Vendor.objects.filter(user=request.user).exists():
                raise ValidationError("You already have a vendor profile")

            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

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
    seriaalizer_class = ProductDetailSerializer
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
    lookup_field = 'slug'

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
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user.id)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            try:
                order = serializer.save()
                return Response(
                    self.get_serializer(order).data,
                    status=status.HTTP_201_CREATED
                )
            except Exception as e:
                return Response(
                    {'detail': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.azampay = Azampay(
            app_name=settings.AZAMPAY_CONFIG['APP_NAME'],
            client_id=settings.AZAMPAY_CONFIG['CLIENT_ID'],
            client_secret=settings.AZAMPAY_CONFIG['CLIENT_SECRET'],
            sandbox=settings.AZAMPAY_CONFIG['ENVIRONMENT'],
        )

    def create(self, request, *args,**kwargs ):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            #create payment record
            payment = serializer.save(
                status='pending'
            )

            #initiate payment with azampay
            payment_response = self.azampay.mobile_checkout(
                amount = float(payment.amount),
                mobile = payment.phone_number,
                provider = settings.AZAMPAY_CONFIG['PROVIDER'],
                external_id = payment.order.id,
            )
            #check azampay response and update the payment record
            if payment_response.get('success'):
                payment.transaction_id = payment_response.get('transactionId')
                payment.status = 'COMPLETED'
                payment.save()
            else:
                payment.delete()
                return Response({
                    'status': 'error',
                    'message': 'Failed to initiate payment',
                    'azampay_response': payment_response
                }, status=status.HTTP_400_BAD_REQUEST)


            # Prepare success response
            response_data = {
                'id': payment.id,
                'amount': payment.amount,
                'phone_number': payment.phone_number,
                'order': payment.order.id,
                'status': payment.status,
                'azampay_response': payment_response
            }

            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            #if payment was created but azampay call failed, delete the payment
            if 'payment' in locals():
                payment.delete()
            return Response({'status': 'error','message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'])
    def webhook(self, request):
        try:
            order_id = request.data.get('externalId')
            transaction_status = request.data.get('transactionStatus')

            if not order.id or not transaction_status:
                return Response({
                    'status': 'error',
                    'message': 'Missing required fields',
                }, status=status.HTTP_400_BAD_REQUEST)

            payment = Payment.objects.get(order_id=order_id)

            # Map Azampay transaction status to payment status
            if transaction_status.lower() == 'success':
                payment.status = 'COMPLETED'
            elif transaction_status.lower() == 'failed':
                payment.status = 'FAILED'
            else:
                payment.status = 'PENDING'

            payment.save()

            return Response({'status': 'success'})

        except Exception as e:
            return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class CustomerRegistrationView(generics.CreateAPIView):
    serializer_class = CustomerRegisterSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            customer = serializer.save()

            #generate tokens
            refresh = RefreshToken.for_user(customer.user)
            access_token = str(refresh.access_token)
            refresh_token= str(refresh)

            login(request, customer.user,backend='django.contrib.auth.backends.ModelBackend')
            return Response(
                {

                    'user': {
                        'id': customer.id,
                        'username': customer.user.username,
                        'address': customer.address,
                        'tokens': {
                            'access': access_token,
                            'refresh': refresh_token
                        }
                    }
                },
                status=status.HTTP_201_CREATED
            )
        return Response(
            {
                'status': 'error',
                'message': 'registration failed',
                'errors': serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )

class CustomerLoginView(generics.CreateAPIView):
    serializer_class = CustomerLoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)

        if serializer.is_valid():
            try:
                # Authenticate user
                user = serializer.authenticate(
                    request,
                    username=serializer.validated_data['username'],
                    password=serializer.validated_data['password']
                )

                if user is None:
                    return Response(
                        {
                            'status': 'error',
                            'message': 'Invalid credentials'
                        },
                        status=status.HTTP_401_UNAUTHORIZED
                    )
                    #generate tokens
                refresh = RefreshToken.for_user(user)
                access_token = str(refresh.access_token)
                refresh_token= str(refresh)
                # Log the user in
                login(request, user)

                return Response(
                    {

                        'user': {
                            'id': user.id,
                            'username': user.username,
                            'email': user.email,
                            'tokens': {
                                'access': access_token,
                                'refresh': refresh_token
                            }
                        }
                    },
                    status=status.HTTP_200_OK
                )

            except Exception as e:
                return Response(
                    {
                        'status': 'error',
                        'message': 'Login failed',
                        'detail': str(e)
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        return Response(
            {
                'status': 'error',
                'message': 'Invalid data',
                'errors': serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )


class CustomerLogoutView(APIView):
    """
    API view to handle logout by blacklisting the refresh token.
    Requires authenticated users.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')

            if not refresh_token:
                return Response(
                    {'status': 'error', 'message': 'Refresh token is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response(status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {
                    'status': 'error',
                    'message': 'Logout failed',
                    'detail': str(e)
                },
                status=status.HTTP_400_BAD_REQUEST
            )
