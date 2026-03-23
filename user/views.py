from django.http import JsonResponse, Http404
from django.contrib.auth import login
from django.shortcuts import get_object_or_404
from django.template.loader import get_template
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.core.mail import EmailMessage
from helperFunctions.validations import *
from helperFunctions.pagination import *
from helperFunctions.roles import *
from .utility import get_tokens_for_user
from utils.permissions import role_required
import logging
# Create your views here.

logger = logging.getLogger(__name__)
today = datetime.today().strftime('%Y-%m-%d')
User = get_user_model()
ROLE_CHOICES = ["super_admin", "weight_man", "purchaser", "inspector", "purchase_head", "supervisor", "factory_manager", "finance", "manager"]

@api_view(['POST'])
@permission_classes([IsAuthenticated, role_required(["super_admin"])])
def add_user(request):
    """
    {fname: "", lname: "", email: "", phone: "", role: "", signature: "", password: ""}
    """
    try:
        serializer = AddUserSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            # Send email
            context = {
                "first_name": user.first_name.capitalize(),
                "last_name": user.last_name.capitalize(),
                "email": user.email,
                "password": request.data.get("password")
            }

            serializer = UserSerializer(user).data

            template = get_template("email-template.html")
            message_content = template.render(context)

            email = EmailMessage(
                "Your Account Credentials",
                message_content,
                "natnaelabebelab@gmail.com",
                [user.email]
            )
            email.content_subtype = "html"
            email.send()

            return JsonResponse(
                {
                    "result": "success",
                    "message": "User registered successfully. Credentials sent via email.",
                    "data": serializer
                },
                status=status.HTTP_201_CREATED
            )

        return JsonResponse(
            {
                "result": "error",
                "errors": serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error("Error occurred while registering user: %s", e)
        return JsonResponse({"result": "error", "message": "Error occurred while registering user"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated, role_required(["super_admin", "manager", "supervisor"])])
def get_users(request):
    try :
        users = User.objects.all().order_by("-record_time")
        paginated_users = user_pagination(request, users)

        return JsonResponse({
            "result": "success",
            "data": paginated_users.data
        })
    except Exception as e:
        logger.error("Error occurred while fetching users: %s", e)
        return JsonResponse({
            "result": "error",
            "data": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PUT'])
@permission_classes([IsAuthenticated, role_required(["super_admin"])])
def update_user(request) :
    try:
        user_id = request.data.get("_id")
        if not user_id or not is_valid_uuid(user_id):
            raise ValueError("Invalid Record ID")

        user = get_object_or_404(User, id=user_id)
        serializer = UserUpdateSerializer(user, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return JsonResponse({"result": "success", "message": "User updated successfully", "data": serializer.data},
                            status=status.HTTP_200_OK)

        logger.error("Error occurred while updating user: %s", serializer.errors)
        return JsonResponse({"result": "error", "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    except Http404:
        return JsonResponse({"result": "error", "message": "Record is not found"}, status=status.HTTP_404_NOT_FOUND)
    except ValueError:
        return JsonResponse({"result": "error", "message": "Invalid user ID"}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error("Error occurred while updating user: %s", e)
        return JsonResponse({"result": "error", "message": "Error occurred while updating user"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated, role_required(["super_admin"])])
def delete_user(request, user_id):
    try:
        if not is_valid_uuid(user_id):
            raise ValueError("Invalid user ID")

        user = get_object_or_404(CustomUser.all_objects, id=user_id)

        user.delete()
        return JsonResponse(
            {"result": "success", "message": "User deleted successfully"},
            status=status.HTTP_200_OK
        )
    except ValueError:
        return JsonResponse({"result": "error", "message": "Invalid user ID"}, status=status.HTTP_400_BAD_REQUEST)
    except Http404:
        return JsonResponse({"result": "error", "message": "Record is not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Error occurred while deleting record: %s", e)
        return JsonResponse({"result": "error", "message": "Error occurred while deleting record"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin"])])
def restore_user(request) :
    """
        Restore a soft-deleted user.
        Expects: {"email": "..."}
        """
    serializer = RestoreUserSerializer(data=request.data)
    if not serializer.is_valid():
        return JsonResponse(
            {"result": "error", "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    email = serializer.validated_data["email"].lower()

    try:
        user = get_object_or_404(User.all_objects, email=email)
        user.restore()  # Calls your model's restore() method
        return JsonResponse(
            {"result": "success", "message": "User record restored successfully"},
            status=status.HTTP_200_OK
        )
    except Exception as e:
        logger.error("Error occurred while restoring user: %s", e)
        return JsonResponse(
            {"result": "error", "message": "Unexpected error occurred while restoring user"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
def user_login(request) :
    """
    Login endpoint: uses serializer validation, Django session, and JWT.
    Expects: {"email": "...", "password": "..."}
    """
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return JsonResponse(
            {"result": "error", "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    email = serializer.validated_data["email"].lower()
    password = serializer.validated_data["password"]

    try:
        # Get a user who is not soft-deleted
        user = User.objects.filter(Q(username=email) & Q(is_deleted=False)).first()
        if not user:
            return JsonResponse(
                {"result": "error", "message": "Email is not registered or user is deleted"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check password
        if not user.check_password(password):
            return JsonResponse(
                {"result": "error", "message": "Invalid password"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Session login
        login(request, user)  # sets session cookie

        # JWT tokens (optional)
        tokens = get_tokens_for_user(user)
        serializer = UserSerializer(user)

        return JsonResponse(
            {
                "result": "success",
                "message": "Logged in successfully",
                "logged_user": serializer.data,
                "tokens": tokens
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error("Error occurred while logging in: %s", e)
        return JsonResponse(
            {"result": "error", "message": "Unexpected server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['PUT'])
@permission_classes([IsAuthenticated, role_required(["super_admin"])])
def update_profile(request) :
    """
    Expected request body:
    {
      "fname": "John",
      "lname": "Doe",
      "email": "john@gmail.com",
      "phone": "123",
      "signature": "abc"
    }
    """
    try:
        serializer = UserProfileSerializer(
            request.user,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return JsonResponse(
                {
                    "result": "success",
                    "message": "Profile updated successfully",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )
        return JsonResponse(
            {
                "result": "error",
                "message": "Error occurred while updating profile",
                "data": serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error("Error occurred while updating profile: %s", e)
        return JsonResponse({"result": "error", "message": "Error occurred while updating profile"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, role_required(["super_admin"])])
def change_password(request) :
    """
    Expects: {"old_password": "...", "new_password": "..."}
    """
    try:
        user = request.user
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")

        if not user:
            return JsonResponse(
                {"result": "error", "message": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        if not old_password or not new_password:
            return JsonResponse(
                {"result": "error", "message": "All fields are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = get_object_or_404(User, username=user.username)

        if not user.check_password(old_password):
            return JsonResponse(
                {"result": "error", "message": "Invalid old password"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.save()

        context = {
            "first_name": user.first_name.capitalize(),
            "last_name": user.last_name.capitalize(),
            "email": user.email,
            "password": new_password
        }

        template = get_template("email-template.html")
        message_content = template.render(context)

        email = EmailMessage(
            "Your Have Changed Your Password",
            message_content,
            "natnaelabebelab@gmail.com",
            [user.email]
        )
        email.content_subtype = "html"
        email.send()

        return JsonResponse(
            {"result": "success", "message": "Password changed successfully"},
            status=status.HTTP_200_OK
        )
    except Http404:
        return JsonResponse({"result": "error", "message": "User not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error("Error occurred while changing password: %s", e)
        return JsonResponse({"result": "error", "message": "Error occurred while changing password"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(["GET"])
def get_role_options(request):
    """
    Returns all available user roles for UI select dropdown.
    Output format: [{"value": "admin", "label": "Admin"}, ...]
    """
    try:
        roles = CustomUser.get_role_options()
        return JsonResponse(
            {"result": "success", "roles": roles},
            status=status.HTTP_200_OK
        )
    except Exception as e:
        # Log unexpected errors
        import logging
        logger = logging.getLogger(__name__)
        logger.error("Error fetching role options: %s", e)
        return JsonResponse(
            {"result": "error", "message": "Could not fetch role options"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_me(request, user_id):
    """
    Get logged user
    """
    if not is_valid_uuid(user_id):
        return JsonResponse(
            {"result": "error", "message": "Invalid user ID"},
            status=status.HTTP_400_BAD_REQUEST
        )
    try:
        user = get_object_or_404(User, id=user_id)
        serializer = UserSerializer(user)
        return JsonResponse(
            {"result": "success", "data": serializer.data},
            status=status.HTTP_200_OK
        )
    except Exception as e:
        logger.error("Error occurred while fetching user: %s", e)

@ensure_csrf_cookie
def csrf_token_view(request):
    return JsonResponse({"message": "CSRF cookie set"})