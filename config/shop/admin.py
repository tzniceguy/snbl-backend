from django.contrib import admin
from .models import CustomUser,Customer,Vendor,Product,Order,Payment
# Register your models here.

admin.site.register(CustomUser)
admin.site.register(Customer)
admin.site.register(Vendor)
admin.site.register(Product)
admin.site.register(Order)
admin.site.register(Payment)
