from user.models import CustomUser

def get_user_role(username):
    # Check if the user with the given username exists
    user = CustomUser.objects.filter(username=username).first()

    if user:
        # If the user exists, retrieve the role
        role = user.role
        return role
    else:
        return None
    