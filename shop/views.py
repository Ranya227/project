from django.shortcuts import render , get_object_or_404
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import sections, Cart, Order,Products
from .serializers import SectionSerializer, CartSerializer, OrderSerializer, ProductSerializer
from rest_framework import status
from django.db import transaction 
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User 
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from django.contrib.auth import authenticate, get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
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



def product_list(request):
    products = Products.objects.all()
    all_sections = sections.objects.all()
    return render(request, 'shop/product_list.html', {
        'products': products,
        'sections': all_sections
    })

@extend_schema(responses=ProductSerializer(many=True))
@api_view(['GET'])
def product_api_list(request):
    products = Products.objects.all()
    serializer = ProductSerializer(products, many=True)
    return Response(serializer.data)

@extend_schema(responses=SectionSerializer(many=True))
@api_view(['GET'])
def section_api_list(request):
    all_sections = sections.objects.all()
    serializer = SectionSerializer(all_sections, many=True)
    return Response(serializer.data)

@extend_schema(responses=CartSerializer)
@api_view(['GET'])
def user_cart_api(request):
    try:
        cart = Cart.objects.get(user=request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data)
    except Cart.DoesNotExist:
        return Response({"error": "السلة غير موجودة لهذا المستخدم"}, status=404)

@extend_schema(responses=OrderSerializer(many=True))
@api_view(['GET'])
def user_orders_api(request):
    orders = Order.objects.filter(user=request.user)
    serializer = OrderSerializer(orders, many=True)
    return Response(serializer.data)

@extend_schema(request=AddToCartRequestSerializer, responses={200: dict})
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

@extend_schema(request=None, responses={201: dict})
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
        "status": "success",
        "message": "تم إتمام الطلب بنجاح!",
        "order_id": new_order.order_id, 
        "total_amount": total
    }, status=status.HTTP_201_CREATED)

@extend_schema(request=RegisterRequestSerializer, responses={201: dict})
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

@extend_schema(request=LoginRequestSerializer, responses={200: {"token": "string"}})
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
    # هذا السطر ضروري ليظهر زر "Upload" في Swagger
    parser_classes = [MultiPartParser]

    def post(self, request):
        # إعداد المفتاح
        genai.configure(api_key="AIzaSy...") 
        model = genai.GenerativeModel('gemini-1.5-flash')

        # استقبال الصور من الطلب
        user_file = request.FILES.get('user_image')
        cloth_file = request.FILES.get('cloth_image')

        # تحقق من وجود الصور لتجنب الأخطاء
        if not user_file or not cloth_file:
            return Response({"error": "Please upload both user and cloth images"}, status=400)

        # تحويل الصور وتحليلها بواسطة Gemini
        user_img = {'mime_type': 'image/jpeg', 'data': user_file.read()}
        cloth_img = {'mime_type': 'image/jpeg', 'data': cloth_file.read()}

        # الـ Prompt الذي يركز على مشروعك (VTON)
        prompt = (
            "You are a professional VTON (Virtual Try-On) assistant. "
            "Analyze the person's features and the clothing item provided. "
            "Generate a highly detailed English prompt for an AI image generator. "
            "The result must show the exact person from the first image wearing the exact clothing from the second image. "
            "Maintain body proportions and facial identity strictly."
        )

        response = model.generate_content([prompt, user_img, cloth_img])

        return Response({"generated_prompt": response.text})