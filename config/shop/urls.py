from django.urls import path, include
from . import views
from rest_framework.routers import DefaultRouter


router = DefaultRouter()
router.register('customers', views.CustomerViewSet, basename='customer')
router.register('vendors', views.VendorViewSet, basename='vendor')
router.register('products', views.ProductViewSet, basename='product')
router.register('orders', views.OrderViewSet, basename='order')
router.register('payments', views.PaymentViewSet, basename='payment')



urlpatterns = [
	path('', include(router.urls)),
	path('register/', views.CustomerRegistrationView.as_view()),
	path('login/', views.CustomerLoginView.as_view()),
]
