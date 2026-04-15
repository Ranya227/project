from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    User_id = models.AutoField(primary_key=True)
    phone_number = models.CharField(max_length=15, blank=True)
    address = models.CharField(max_length=255, blank=True)
    def __str__(self):
        return self.username

class sections(models.Model):
    sections_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=20, blank=False)
    description = models.TextField(max_length=255, blank=False)
    def __str__(self):
        return self.name



class Products(models.Model):
    Products_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=20, blank=False)
    description = models.TextField(max_length=255, blank=False)
    price = models.DecimalField(max_digits=10, decimal_places=3)
    price_after_discount = models.DecimalField(max_digits=10, decimal_places=3)
    section = models.ForeignKey(sections, on_delete=models.CASCADE, related_name='products_in_section')
    
    def __str__(self):
        return self.name
    
class ProductImage(models.Model):
    product = models.ForeignKey(Products, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/gallery/')
    is_cover = models.BooleanField(default=False) 
    def __str__(self):
        return f"Image for {self.product.name}"



class Cart(models.Model):
    cart_id = models.AutoField(primary_key=True)
    shipping = models.DecimalField(max_digits=10, decimal_places=3, default=0.000)
    cart_total_price = models.DecimalField(max_digits=10, decimal_places=3, default=0.000)
    cart_total_price_after_discount = models.DecimalField(max_digits=10, decimal_places=3, default=0.000)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    products = models.ManyToManyField(Products, related_name='carts_containing_product', blank=True)
    def __str__(self):
        return f"Cart of {self.user.username}"

class Payment(models.Model):
    payment_id = models.AutoField(primary_key=True)
    payment_name = models.CharField(max_length=50)
    payment_image = models.ImageField(upload_to='payments/receipts/', blank=True, null=True)
    payment_url = models.URLField(max_length=500, blank=True, null=True)
    def __str__(self):
        return self.payment_name

class Order(models.Model):
    order_id = models.AutoField(primary_key=True)
    order_status = models.CharField(max_length=50, default='Pending')
    payment_method = models.CharField(max_length=50)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0) 
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, related_name='orders_with_payment')
    order_items = models.ManyToManyField(Products, related_name='orders_containing_item')

    def __str__(self):
        return f"Order {self.order_id} by {self.user.username}"


class Variant(models.Model):
   variant_id = models.AutoField(primary_key=True)
   size = models.CharField(max_length=20, blank=True, null=True)
   colors = models.CharField(max_length=50, blank=True, null=True)
   product = models.ForeignKey(Products, on_delete=models.CASCADE, related_name='variants')
   def __str__(self):
    return f"{self.product.name} - {self.size} / {self.colors}"
