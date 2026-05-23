from django.shortcuts import render, get_object_or_404
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

User = get_user_model()

# --- Serializers ---
class VtonTryOnSerializer(serializers.Serializer):
    user_image = serializers.ImageField()
    cloth_image = serializers.ImageField()

# --- Existing API Views (Keep them as they are) ---
@api_view(['GET'])
def product_api_list(request):
    products = Products.objects.all()
    return Response(ProductSerializer(products, many=True).data)

@api_view(['GET'])
def section_api_list(request):
    return Response(SectionSerializer(sections.objects.all(), many=True).data)

# --- The New Working VTON View ---
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
                for chunk in user_img.chunks():
                    user_tmp.write(chunk)
                user_path = user_tmp.name

            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as cloth_tmp:
                for chunk in cloth_img.chunks():
                    cloth_tmp.write(chunk)
                cloth_path = cloth_tmp.name

            
            client = Client("yisol/IDM-VTON")
            
            result = client.predict(
                dict={"background": handle_file(user_path), "layers": [], "composite": None},
                garm_img=handle_file(cloth_path),
                garment_des="clothing item",
                is_checked=True,
                is_checked_det=True,
                num_inference_steps=30,
                api_name="/tryon"
            )

            
            return Response({
                "status": "success",
                "result": result[0] if isinstance(result, tuple) else result
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": f"VTON failed: {str(e)}"}, status=500)
        finally:
           
            if 'user_path' in locals(): os.unlink(user_path)
            if 'cloth_path' in locals(): os.unlink(cloth_path)