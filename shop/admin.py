from django.contrib import admin
from .models import User, sections, Products, ProductImage, Cart, Payment, Order, Variant

admin.site.register(User)
admin.site.register(sections)
admin.site.register(Payment)
admin.site.register(Cart)

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

@admin.register(Products)
class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductImageInline]
    list_display = ('name', 'price', 'section')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'user', 'order_status', 'payment_method')
    list_filter = ('order_status', 'payment_method')

admin.site.register(Variant)