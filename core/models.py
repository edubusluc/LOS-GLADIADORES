from django.db import models
from django.utils.crypto import get_random_string
from django.contrib.auth.models import AbstractUser

# Create your models here.
# class CustomUser(AbstractUser):
#     email = models.EmailField(unique=True)
#     reset_password_token = models.CharField(max_length=255, blank=True, null=True)

#     def generate_reset_password_token(self):
#         token = get_random_string(length=32)

#         # Asignar el token al usuario
#         self.reset_password_token = token
#         self.save()