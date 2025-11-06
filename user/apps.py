from django.apps import AppConfig

class UserConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'user'
    
    def ready(self):
        from .startup import create_default_users
        create_default_users()