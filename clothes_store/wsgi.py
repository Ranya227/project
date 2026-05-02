"""
WSGI config for clothes_store project.
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'clothes_store.settings')

application = get_wsgi_application()

try:
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    username = 'ranya'
    password = '1234'
    email = 'ranya@example.com'

    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(username=username, email=email, password=password)
        print(f" Success: Superuser '{username}' has been created.")
    else:
        print(f" Info: Superuser '{username}' already exists.")
        
except Exception as e:
    print(f"Error creating superuser: {e}")