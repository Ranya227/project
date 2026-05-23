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
import google.generativeai as genai
import os

User = get_user_model()

class LoginRequestSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

class RegisterRequestSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
    email = serializers.EmailField()

class AddToCartRequestSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(default=1)

class VtonTryOnSerializer(serializers.Serializer):
    user_image = serializers.ImageField(help_text="Upload the person's photo")
    cloth_image = serializers.ImageField(help_text="Upload the clothing item photo")


def product_list(request):
    products = Products.objects.all()
    all_sections = sections.objects.all()
    return render(request, 'shop/product_list.html', {
        'products': products,
        'sections': all_sections
    })

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
    quantity_to_add = int(request.data.get('quantity', 1))
    
    product = get_object_or_404(Products, Products_id=product_id)
    cart, created = Cart.objects.get_or_create(user=request.user)

    if cart.products.filter(Products_id=product_id).exists():
        message = f"Updated {product.name} quantity."
    else:
        cart.products.add(product)
        message = f"Added {product.name} to cart."
    
    cart.save()
    return Response({
        "status": "success",
        "message": message,
        "current_cart_count": cart.products.count()
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
def checkout_api(request):
    user = request.user
    try:
        cart = Cart.objects.get(user=user)
        if not cart.products.exists():
            return Response({"error": "Cart is empty"}, status=400)
    except Cart.DoesNotExist:
        return Response({"error": "No cart found"}, status=404)

    with transaction.atomic():
        new_order = Order.objects.create(
            user=user,
            order_status='Pending',       
            payment_method='Cash on Delivery' 
        )

        total = 0
        for product in cart.products.all():
            new_order.order_items.add(product) 
            total += product.price 
        
        new_order.total_price = total
        new_order.save()

        cart.products.clear()
        cart.save()
        
        return Response({
            "status": "success",
            "message": "Order completed",
            "order_id": new_order.order_id, 
            "total_amount": total
        }, status=status.HTTP_201_CREATED)

@api_view(['POST'])
def register_api(request):
    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email')
    
    if User.objects.filter(username=username).exists():
        return Response({"error": "Username exists"}, status=400)
    
    user = User.objects.create_user(username=username, password=password, email=email)
    token, created = Token.objects.get_or_create(user=user)
    return Response({"token": token.key}, status=201)

@api_view(['POST'])
def login_api(request):
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(username=username, password=password)
    if user:
        token, created = Token.objects.get_or_create(user=user)
        return Response({"token": token.key})
    return Response({"error": "Invalid credentials"}, status=400)


class VtonPromptView(APIView):
    parser_classes = [MultiPartParser]
    serializer_class = VtonTryOnSerializer
    
    def post(self, request):
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            return Response({"error": "API Key not configured on server"}, status=500)

        serializer = VtonTryOnSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_file = serializer.validated_data['user_image']
        cloth_file = serializer.validated_data['cloth_image']

        genai.configure(api_key=api_key)
        
        user_img_bytes = user_file.read()
        user_img_data = {'mime_type': 'image/jpeg', 'data': user_img_bytes}

        cloth_img_bytes = cloth_file.read()
        cloth_img_data = {'mime_type': 'image/jpeg', 'data': cloth_img_bytes}

        prompt = (
            "You are a professional Virtual Try-On system. "
            "Describe the person in the first image wearing the exact clothing from the second image. "
            "Create a detailed prompt for image generation."
        )

        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content([prompt, user_img_data, cloth_img_data])
            return Response({
                "status": "success",
                "generated_prompt": response.text
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            try:
                model_alt = genai.GenerativeModel('gemini-pro-vision')
                response = model_alt.generate_content([prompt, user_img_data, cloth_img_data])
                return Response({
                    "status": "success",
                    "generated_prompt": response.text
                }, status=status.HTTP_200_OK)
            except Exception as final_e:
                return Response({"error": f"API Error: {str(e)}"}, status=500)