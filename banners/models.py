from django.db import models

# Create your models here.
class Banner(models.Model):
    name = models.CharField(max_length=255)
    image = models.ImageField(upload_to='banners/')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
