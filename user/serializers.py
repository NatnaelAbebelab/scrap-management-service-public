from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import CustomUser

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = '__all__'  # Include all fields

class UserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        exclude = ["password"]

class AddUserSerializer(serializers.ModelSerializer):
    fname = serializers.CharField(source="first_name")
    lname = serializers.CharField(source="last_name")
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["fname", "lname", "email", "phone", "role", "signature", "password"]

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered")
        return value.lower()

    def validate_role(self, value):
        valid_roles = [choice[0] for choice in User.ROLE_CHOICES]
        if value not in valid_roles:
            raise serializers.ValidationError("Invalid role selected")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        validated_data["username"] = validated_data["email"]

        user = User.objects.create_user(
            password=password,
            **validated_data
        )

        return user

class UserUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    first_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    last_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    role = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    signature = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone", "role", "signature", "password"]

    def validate_email(self, value):
        user = self.instance
        if User.objects.filter(email=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("Email already registered")
        return value.lower()

    def validate_role(self, value):
        if not value:  # skip null or blank
            return value
        valid_roles = [choice[0] for choice in User.ROLE_CHOICES]
        if value not in valid_roles:
            raise serializers.ValidationError("Invalid role selected")
        return value

    def update(self, instance: User, validated_data):
        password = validated_data.pop("password", None)
        if "email" in validated_data and validated_data["email"]:
            validated_data["username"] = validated_data["email"]
        for attr, value in validated_data.items():
            if value is not None:
                setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

class UserProfileSerializer(serializers.ModelSerializer):
    fname = serializers.CharField(source="first_name", required=False)
    lname = serializers.CharField(source="last_name", required=False)
    email = serializers.EmailField(required=False)
    phone = serializers.CharField(required=False)
    signature = serializers.CharField(required=False)

    class Meta:
        model = User
        fields = ["fname", "lname", "email", "phone", "signature"]

    def validate_email(self, value):
        user = self.instance
        if User.objects.filter(email=value).exclude(id=user.id).exists():
            raise serializers.ValidationError("Email already used")
        return value

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            if attr in ["first_name", "last_name", "phone", "signature"] and value is not None:
                setattr(instance, attr, value)

        email = validated_data.get("email")
        if email:
            instance.email = email
            instance.username = email

        instance.save()
        return instance

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

class RestoreUserSerializer(serializers.Serializer):
    email = serializers.EmailField()
