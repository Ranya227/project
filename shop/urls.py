from django.urls import path 
from . import views

urlpatterns = [
   
    path('', views.product_list, name='product_list'),
 
    path('api/products/', views.product_api_list, name='product_api_list'),
    path('api/sections/', views.section_api_list, name='section_api_list'),
    path('api/cart/', views.user_cart_api, name='user_cart_api'),
    path('api/orders/', views.user_orders_api, name='user_orders_api'),

    path('api/add-to-cart/', views.add_to_cart_api, name='add_to_cart_api'),
    path('api/checkout/', views.checkout_api, name='checkout_api'),

    path('api/register/', views.register_api, name='register_api'),
    path('api/login/', views.login_api, name='login_api'),
]