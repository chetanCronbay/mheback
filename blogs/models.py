from django.db import models
from products.models import Category 

def blog_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return f'user_banner{instance.user.id}/{filename}'

class Blog(models.Model):
    blog_title = models.CharField(max_length=100)
    blog_category = models.ForeignKey(Category,on_delete=models.CASCADE, related_name='blogCategory', help_text="Blog category")
    image1 = models.ImageField(max_length=500, null=False, blank=False, upload_to=blog_path)
    description = models.TextField(null=True, blank=True)
    meta_title = models.CharField(max_length=200, null=True, blank=True)
    description1 = models.CharField(max_length=500, null=True, blank=True)
    blog_url = models.CharField(max_length=200, unique=True)
    tags = models.CharField(max_length=100, null=True, blank=True)
    author_name = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'blog_blog'
