from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import sections, Cart, Order, Products, ProductImage
from .serializers import SectionSerializer, CartSerializer, OrderSerializer, ProductSerializer
from rest_framework import status, serializers
from django.db import transaction 
from django.contrib.auth import authenticate, get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
import replicate
import os

User = get_user_model()

# --- Serializers ---
class LoginRequestSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

class RegisterRequestSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
    email = serializers.EmailField()

class VtonTryOnSerializer(serializers.Serializer):
    user_image = serializers.ImageField()
    cloth_image = serializers.ImageField()

# --- Shop Views (Frontend) ---
def product_list(request):
    products = Products.objects.all()
    all_sections = sections.objects.all()
    return render(request, 'shop/product_list.html', {
        'products': products,
        'sections': all_sections
    })

# --- API Views ---
@api_view(['GET'])
def product_api_list(request):
    products = Products.objects.all()
    serializer = ProductSerializer(products, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def section_api_list(request):
    all_sections = sections.objects.all()
    serializer = SectionSerializer(all_sections, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def user_cart_api(request):
    try:
        cart = Cart.objects.get(user=request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data)
    except Cart.DoesNotExist:
        return Response({"error": "Cart not found"}, status=404)

@api_view(['GET'])
def user_orders_api(request):
    orders = Order.objects.filter(user=request.user)
    serializer = OrderSerializer(orders, many=True)
    return Response(serializer.data)

@api_view(['POST'])
def add_to_cart_api(request):
    product_id = request.data.get('product_id')
    product = get_object_or_404(Products, Products_id=product_id)
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart.products.add(product)
    cart.save()
    return Response({"status": "success", "message": f"Added {product.name} to cart."}, status=200)

@api_view(['POST'])
def checkout_api(request):
    user = request.user
    cart = get_object_or_404(Cart, user=user)
    with transaction.atomic():
        new_order = Order.objects.create(user=user, order_status='Pending', payment_method='Cash on Delivery')
        total = 0
        for product in cart.products.all():
            new_order.order_items.add(product)
            total += product.price
        new_order.total_price = total
        new_order.save()
        cart.products.clear()
        return Response({"status": "success", "order_id": new_order.order_id, "total": total}, status=201)

# --- Auth API ---
@api_view(['POST'])
def register_api(request):
    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email')
    if User.objects.filter(username=username).exists():
        return Response({"error": "Username exists"}, status=400)
    user = User.objects.create_user(username=username, password=password, email=email)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key}, status=201)

@api_view(['POST'])
def login_api(request):
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(username=username, password=password)
    if user:
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key})
        return Response({"error": "Invalid credentials"}, status=400)

# --- VTON (Virtual Try-On) ---
class VtonPromptView(APIView):
    parser_classes = [MultiPartParser]
    serializer_class = VtonTryOnSerializer
    
    def post(self, request):
        replicate_token = os.environ.get("REPLICATE_API_TOKEN")
        if not replicate_token:
            return Response({"error": "Replicate Token not found on server"}, status=500)

        serializer = VtonTryOnSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_img = request.FILES['user_image']
        cloth_img = request.FILES['cloth_image']

        try:
            output = replicate.run(
                "yisol/idm-vton:8a89b0ab59a037c0f3d083cd0da9a05a1bfbcd61f5bc12627b83500b21da8ad4",
                input={
                    "human_img": user_img,
                    "garm_img": cloth_img,
                    "garment_des": "clothing item",
                    "is_checked": True,
                    "is_checked_det": True,
                    "num_inference_steps": 30
                }
            )

            return Response({
                "status": "success",
                "result_image_url": output[0] if isinstance(output, list) else output
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({"error": f"VTON Execution Failed: {str(e)}"}, status=500)