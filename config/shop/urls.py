from django.urls import path, include
from .views import UserViewSet,CustomerViewSet,VendorViewSet,ProductViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'customers', CustomerViewSet)
router.register(r'vendors', VendorViewSet)
router.register(r'products', ProductViewSet)

urlpatterns = [
	path('', include(router.urls)),
]