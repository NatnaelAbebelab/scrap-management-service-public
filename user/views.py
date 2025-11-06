from django.contrib.auth.models import User
from django.http import JsonResponse, Http404
from django.contrib.auth import login
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.core.exceptions import ValidationError
from datetime import datetime
from django.template.loader import get_template
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.contrib.auth.hashers import make_password, check_password
from django.core.mail import EmailMessage
from django.contrib.auth import get_user_model
from helperFunctions.material_type import *
from helperFunctions.grade_type import *
from helperFunctions.validations import *
from helperFunctions.pagination import *
from helperFunctions.status import *
from helperFunctions.roles import *
from .utility import get_tokens_for_user
from utils.permissions import role_required
import string, secrets, json, logging
# Create your views here.

logger = logging.getLogger(__name__)
today = datetime.today().strftime('%Y-%m-%d')
User = get_user_model()
ROLE_CHOICES = ["super_admin", "weight_man", "purchaser", "inspector", "purchase_head", "supervisor", "factory_manager", "finance", "manager"]
@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin"])])
def add_user(request):
    if request.method == "POST":
        fname = request.POST.get("fname", "").strip()
        lname = request.POST.get("lname", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("phone", "").strip()
        role = request.POST.get("role", "purchaser").strip().lower()  # Default role if not provided
        
        try:
            # Check if role is valid
            if role not in ROLE_CHOICES:
                return JsonResponse({"result": "error", "message": f"Selected role {role} is unknown"}, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if the email or username already exists
            if User.objects.filter(email=email).exists():
                return JsonResponse({"result": "error", "message": f"User email {email} is already registered"}, status=status.HTTP_400_BAD_REQUEST)

            if User.objects.filter(username=email).exists():
                return JsonResponse({"result": "error", "message": f"User email {email} is already registered"}, status=status.HTTP_400_BAD_REQUEST)
            
            # generate temporary password
            characters = string.ascii_letters + string.digits + "!@#$%^&*"
            password = "".join(secrets.choice(characters) for _ in range(8))
            
            user = User.objects.create(
                first_name=fname,
                last_name=lname,
                email=email,
                phone=phone,
                username=email,
                role=role,
                password=make_password(password),  # Hash password for security
                created_by=request.user.username,
                created_at=today,
                updated_by=request.user.username,
                updated_at=today
            )
            # send email to user email
            context = {
                "fname": fname.capitalize(),
                "lname": lname.capitalize(),
                "email": email,
                "password": password
            }
            template = get_template("email-template.html")
            message_content = template.render(context)
            subject = "Your Account Credentials"
            message = message_content
            email = EmailMessage(subject, message, "natnaelabebelab@gmail.com", [email])
            email.content_subtype = "html"  # Specify that the email content is HTML
            email.send()
            return JsonResponse({"result": "success", "message": f"User is registered successfully. Account credentials are sent to email"}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error("Error occurred while registering user: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while registering user"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['GET'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "manager", "supervisor"])])
def get_users(request):
    try :
        users = User.objects.all().order_by("-record_time")
        paginated_records = user_pagination(request, users)
        return JsonResponse({
            "result": "success",
            "data": paginated_records.data,
        }, status=status.HTTP_200_OK)
    except ValidationError as e:
        # Handle ValidationError and return as string or a simple message
        return JsonResponse({
            "result": "error",
            "data": str(e), # Convert the exception to a string
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return JsonResponse({
            "result": "error",
            "data": e
        }, status=status.HTTP_400_BAD_REQUEST)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin"])])
def update_user(request) :
    if request.method == "PATCH":
        _id = request.POST.get("_id").strip()
        fname = request.POST.get("fname")
        lname = request.POST.get("lname")
        email = request.POST.get("email").strip().lower()
        phone = request.POST.get("phone").strip()
        role = request.POST.get("role").strip().lower()
        
        if not is_valid_uuid(_id):
            return JsonResponse({"result": "error", "message": "Invalid ID of record"}, status=status.HTTP_400_BAD_REQUEST)
        if role and role not in ROLE_CHOICES:
            return JsonResponse({"result": "error", "message": "Role is unknown"}, status=status.HTTP_400_BAD_REQUEST)
        if CustomUser.objects.filter(email=email).exclude(id=_id).exists():
            return JsonResponse({"result": "error", "message": "Email address is already registered"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Retrieve the CustomUser by ID
            user = get_object_or_404(User, id=_id)
            
            fields_and_values = {
                "first_name": fname,
                "last_name": lname,
                "email": email,
                "phone": phone,
                "username": email,
                "role": role
            }
            # Loop through each field and value using zip
            for field, value in fields_and_values.items():
                # Only update the field if the value is not empty
                if value:
                    setattr(user, field, value)
            user.updated_at = today
            # Save the updated user
            user.save()
            return JsonResponse({"result": "success", "message": "user updated successfully"}, status=status.HTTP_200_OK)
        except Http404:
            return JsonResponse({"result": "error", "message": "Record is not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error("Error occurred while updating user: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while updating user"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, role_required(["super_admin"])])
def delete_user(request) :
    if request.method == "DELETE":
        _id = request.POST.get("_id").strip()
        
        if not is_valid_uuid(_id):
            return JsonResponse({"result": "error", "message": "Invalid Record ID"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            get_user = get_object_or_404(User.all_objects, id=_id)
            get_user.delete()
            return JsonResponse({"result": "success", "message": f"User is deleted successfully"}, status=status.HTTP_200_OK)
        except Http404:
            return JsonResponse({"result": "error", "message": "Record is not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error("Error occurred while deleting record: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while deleting record"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin"])])
def restore_user(request) :
    if request.method == "PATCH":
        email = request.POST.get("email").strip().lower()
        
        try:
            get_user = get_object_or_404(User.all_objects, email=email)
            get_user.restore()
            return JsonResponse({"result": "success", "message": f"User record is restored successfully"}, status=status.HTTP_200_OK)
        except Http404:
            return JsonResponse({"result": "error", "message": "Record is not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error("Error occurred while restoring user: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while restoring user"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['POST'])
def user_login(request) :
     if request.method == "POST":
        data = json.loads(request.body)
        email = data.get("email").lower()
        password = data.get("password")
        
        try:
            if not User.objects.filter(email=email).exists() :
                return JsonResponse({"result": "error", "message": "Email is not registered"}, status=status.HTTP_400_BAD_REQUEST)
            user = User.objects.filter(Q(username=email) & Q(is_deleted=False)).first()
            if user:
                if check_password(password, user.password) : #vars(user_)['password']
                    tokens = get_tokens_for_user(user)  # Get JWT tokens
                    login(request, user) # username
                    if request.user == user:
                        role = get_user_role(request.user)
                        return JsonResponse({"result": "success", "message": "logged in", "logged_user": user.username, "tokens": tokens, "role": role}, status=status.HTTP_200_OK)
            return JsonResponse({"result": "error", "message": "user not found"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error("Error occurred while logging in: %s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while logging in"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin"])])
def update_profile(request) :
    if request.method == "PATCH":
        _uname = request.POST.get("logged_user").lower()
        fname = request.POST.get("fname").strip()
        lname = request.POST.get("lname").strip()
        email = request.POST.get("email").strip().lower()
        phone = request.POST.get("phone").strip()
        uname = request.POST.get("uname").strip().lower()
        
        try:
            user = get_object_or_404(User, username=_uname)
            if User.objects.filter(Q(email=email) & ~Q(_id=user._id)).exists() :
                return JsonResponse({"result": "error", "message": "email already used"}, status=status.HTTP_400_BAD_REQUEST)
            if User.objects.filter(Q(username=uname) & ~Q(_id=user._id)).exists() :
                return JsonResponse({"result": "error", "message": "username already used"}, status=status.HTTP_400_BAD_REQUEST)

            for attr, value in [("fname", fname), ("lname", lname), ("email", email), ("phone", phone), ("username", uname)]:
                if value != '':
                    setattr(user, attr, value)
            user.save()
            return JsonResponse({"result": "success", "message": "profile updated successfully", "logged_user": uname}, status=status.HTTP_200_OK)
        except Http404:
            return JsonResponse({"result": "success", "message": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e :
            logger.error("Error occurred while updating profile:%s", e)
            return JsonResponse({"result": "error", "message": "Error occurred while updating profile"}, status=status.HTTP_400_BAD_REQUEST)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin"])])
def change_password(request) :
    if request.method == "PATCH":
        _uname = request.POST.get("logged_user")
        new_password = request.POST.get("new_password")
        old_password = request.POST.get("old_password")
        
        try:
            user = get_object_or_404(User, username=_uname)
            if check_password(old_password, user.password) :
                if new_password:
                    user.password = make_password(new_password)
                    user.save()
                    return JsonResponse({"result": "success", "message": "Password changed"}, status=status.HTTP_200_OK)
            return JsonResponse({"result": "error", "message": "Invalid old password"}, status=status.HTTP_400_BAD_REQUEST)
        except Http404:
            return JsonResponse({"result": "success", "message": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e :
            logger.error("Error occurred while changing password: %s", e)
            return JsonResponse({"result": "error", "message": "Operation failed"}, status=status.HTTP_400_BAD_REQUEST)
            