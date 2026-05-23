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
    product_id = serializers.IntegerField(help_text="ID of the clothing product from database")
    user_image = serializers.ImageField(help_text="Upload the person's photo")


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
        return Response({"error": "السلة غير موجودة لهذا المستخدم"}, status=404)

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
        message = f"تم تحديث كمية {product.name} في السلة."
    else:
        cart.products.add(product)
        message = f"تمت إضافة {product.name} للسلة لأول مرة."
    
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
            return Response({"error": "السلة فارغة، لا يمكنك إتمام الطلب"}, status=400)
    except Cart.DoesNotExist:
        return Response({"error": "لا توجد سلة لهذا المستخدم"}, status=404)

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
            "status": "success", "message": "تم إتمام الطلب بنجاح!",
            "order_id": new_order.order_id, 
            "total_amount": total
        }, status=status.HTTP_201_CREATED)

@api_view(['POST'])
def register_api(request):
    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email')
    
    if User.objects.filter(username=username).exists():
        return Response({"error": "اسم المستخدم موجود مسبقاً"}, status=400)
    
    user = User.objects.create_user(username=username, password=password, email=email)
    token, created = Token.objects.get_or_create(user=user)
    return Response({
        "message": "تم إنشاء الحساب بنجاح",
        "token": token.key
    }, status=201)

@api_view(['POST'])
def login_api(request):
    username = request.data.get('username')
    password = request.data.get('password')
    
    user = authenticate(username=username, password=password)
    if user:
        token, created = Token.objects.get_or_create(user=user)
        return Response({"token": token.key})
    else:
        return Response({"error": "بيانات الدخول غير صحيحة"}, status=400)


class VtonPromptView(APIView):
    parser_classes = [MultiPartParser]
    
    def post(self, request):
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            return Response({"error": "API Key not configured on server"}, status=500)

        serializer = VtonTryOnSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        product_id = serializer.validated_data['product_id']
        user_file = serializer.validated_data['user_image']

        product = get_object_or_404(Products, Products_id=product_id)
        
        product_image_obj = product.images.filter(is_cover=True).first() or product.images.first()
        
        if not product_image_obj:
            return Response({"error": "هذا المنتج لا يحتوي على صور مخزنة في قاعدة البيانات"}, status=400)

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-pro')

        try:
            user_img_bytes = user_file.read()
            user_img_data = {'mime_type': 'image/jpeg', 'data': user_img_bytes}

            with product_image_obj.image.open('rb') as cloth_file:
                cloth_img_bytes = cloth_file.read()
            
            cloth_img_data = {'mime_type': 'image/jpeg', 'data': cloth_img_bytes}

            prompt = (
                f"You are a professional Virtual Try-On (VTON) system. "
                f"Analyze the person's body structure and appearance in the first image, "
                f"and the clothing item named '{product.name}' in the second image. "
                f"Cloth Description: {product.description}. "
                f"Generate a highly detailed, professional English prompt for an AI image generator (like Diffusion models). "
                f"The resulting prompt must explicitly describe the exact person from the first image wearing the exact clothing item from the second image, "
                f"strictly preserving facial features, body proportions, clothing designs, textures, and patterns."
            )

            response = model.generate_content([prompt, user_img_data, cloth_img_data])
            
            return Response({
                "status": "success",
                "product_id": product_id,
                "product_name": product.name,
                "generated_prompt": response.text
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({"error": f"Failed to process VTON: {str(e)}"}, status=500)