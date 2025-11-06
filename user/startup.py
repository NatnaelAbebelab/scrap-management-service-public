from django.contrib.auth import get_user_model
from django.db.utils import OperationalError
from django.contrib.auth.hashers import make_password, check_password
from datetime import datetime
import logging

User = get_user_model()
logger = logging.getLogger(__name__)
today = datetime.today().strftime('%Y-%m-%d')

ROLE_CHOICES = ["super_admin", "weight_man", "purchaser", "inspector", "purchase_head", "supervisor", "finance", "manager"]

def create_default_users():
    default_users = [
        {
            "first_name": "Weight",
            "last_name": "Man",
            "username": "weightman@gmail.com",
            "email": "weightman@gmail.com",
            "role": "weight_man",
            "phone": "0911000000",
            "is_superuser": False,
            "is_staff": True,
            "is_active": True,
            "password": "6imU6U*b"
        },
        {
            "first_name": "Purchaser",
            "last_name": "",
            "username": "purchaser@gmail.com",
            "email": "purchaser@gmail.com",
            "role": "purchaser",
            "phone": "0911000000",
            "is_superuser": False,
            "is_staff": True,
            "is_active": True,
            "password": "RQR0YN%8"
        },
        {
            "first_name": "Inspector",
            "last_name": "",
            "username": "inspector@gmail.com",
            "email": "inspector@gmail.com",
            "role": "inspector",
            "phone": "0911000000",
            "is_superuser": False,
            "is_staff": True,
            "is_active": True,
            "password": "BSlVX6h6"
        },
        {
            "first_name": "Purchase",
            "last_name": "Head",
            "username": "purchasehead@gmail.com",
            "email": "purchasehead@gmail.com",
            "role": "purchase_head",
            "phone": "0911000000",
            "is_superuser": False,
            "is_staff": True,
            "is_active": True,
            "password": "Mqbqys06"
        },
        {
            "first_name": "Supervisor",
            "last_name": "",
            "username": "supervisor@gmail.com",
            "email": "supervisor@gmail.com",
            "role": "supervisor",
            "phone": "0911000000",
            "is_superuser": False,
            "is_staff": True,
            "is_active": True,
            "password": "UvtKztsa"
        },
        {
            "first_name": "Factory",
            "last_name": "Manager",
            "username": "factorymanager@gmail.com",
            "email": "factorymanager@gmail.com",
            "role": "factory_manager",
            "phone": "0911000000",
            "is_superuser": False,
            "is_staff": True,
            "is_active": True,
            "password": "n76EaH#W"
        },
        {
            "first_name": "Finance",
            "last_name": "",
            "username": "finance@gmail.com",
            "email": "finance@gmail.com",
            "role": "finance",
            "phone": "0911000000",
            "is_superuser": False,
            "is_staff": True,
            "is_active": True,
            "password": "bOaM#8VR"
        },
        {
            "first_name": "General",
            "last_name": "Manager",
            "username": "manager@gmail.com",
            "email": "manager@gmail.com",
            "role": "manager",
            "phone": "0911000000",
            "is_superuser": False,
            "is_staff": True,
            "is_active": True,
            "password": "n76EaH#W"
        },
        {
            "first_name": "Super",
            "last_name": "Admin",
            "username": "superadmin1@gmail.com",
            "email": "superadmin1@gmail.com",
            "role": "super_admin",
            "phone": "0911000000",
            "is_superuser": True,
            "is_staff": True,
            "is_active": True,
            "password": "YB&oIXG^"
        },
    ]

    for user_data in default_users:
        try:
            if not User.objects.filter(username=user_data["username"]).exists():
                user = User.objects.create(
                    first_name=user_data["first_name"],
                    last_name=user_data["last_name"],
                    username=user_data["username"],
                    email=user_data["email"],
                    role=user_data["role"],
                    phone=user_data["phone"],
                    password=make_password(user_data["password"]),
                    created_by="auto",
                    created_at=today,
                    updated_by="auto",
                    updated_at=today
                )
                if user_data.get("is_superuser"):
                    user.is_superuser = True
                if user_data.get("is_staff"):
                    user.is_staff = True
                if user_data.get("is_active"):
                    user.is_active = True
                user.save()
        except OperationalError:
            # This handles the case when DB isn't ready yet during migrations
            pass
