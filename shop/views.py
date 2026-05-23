from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import sections, Cart, Order, Products
from .serializers import SectionSerializer, CartSerializer, OrderSerializer, ProductSerializer
from rest_framework import status, serializers
from django.db import transaction 
from django.contrib.auth import authenticate, get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from gradio_client import Client, handle_file
import os
import tempfile
import base64

User = get_user_model()

class VtonTryOnSerializer(serializers.Serializer):
    user_image = serializers.ImageField()
    cloth_image = serializers.ImageField()

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
        return Response(CartSerializer(cart).data)
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
    cart, _ = Cart.objects.get_or_create(user=request.user)
    cart.products.add(product)
    cart.save()
    return Response({"status": "success"}, status=200)

@api_view(['POST'])
def checkout_api(request):
    user = request.user
    cart = get_object_or_404(Cart, user=user)
    with transaction.atomic():
        new_order = Order.objects.create(user=user, order_status='Pending', payment_method='Cash on Delivery')
        total = sum(p.price for p in cart.products.all())
        new_order.total_price = total
        new_order.save()
        cart.products.clear()
        return Response({"status": "success", "total": total}, status=201)

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

class VtonPromptView(APIView):
    parser_classes = [MultiPartParser]
    serializer_class = VtonTryOnSerializer
    
    def post(self, request):
        serializer = VtonTryOnSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            user_img = request.FILES['user_image']
            cloth_img = request.FILES['cloth_image']

            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as user_tmp:
                user_tmp.write(user_img.read())
                user_path = user_tmp.name

            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as cloth_tmp:
                cloth_tmp.write(cloth_img.read())
                cloth_path = cloth_tmp.name

            client = Client("yisol/IDM-VTON")
            result = client.predict(
                dict={"background": handle_file(user_path), "layers": [], "composite": None},
                garm_img=handle_file(cloth_path),
                garment_des="clothing item",
                is_checked=True,
                api_name="/tryon"
            )

            result_path = result[0] if isinstance(result, (list, tuple)) else result
            
            # تحويل ملف الصورة الناتج إلى Base64
            if result_path and os.path.exists(result_path):
                with open(result_path, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                    # إضافة Header ليفهم المتصفح أنها صورة PNG
                    final_image_data = f"data:image/png;base64,{encoded_string}"
            else:
                return Response({"error": "Result file not found on AI server"}, status=500)

            return Response({
                "status": "success",
                "result_image_base64": final_image_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": f"VTON failed: {str(e)}"}, status=500)
        finally:
            if 'user_path' in locals():
                try: os.unlink(user_path)
                except: pass
            if 'cloth_path' in locals():
                try: os.unlink(cloth_path)
                except: pass