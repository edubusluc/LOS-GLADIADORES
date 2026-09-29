from django.db import models
from core.models import Club

# Create your models here.
class Post(models.Model):
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='posts', null=True)
    title = models.CharField(max_length=100)
    content = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Image(models.Model):
    post = models.ForeignKey(Post, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='static/img')