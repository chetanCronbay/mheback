from django.db import models
from products.models import Category  # import Category model

class Blog(models.Model):
    blog_title = models.CharField(max_length=100)
    blog_category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='blogs')
    image1 = models.CharField(max_length=500, null=True, blank=True)
    image2 = models.CharField(max_length=500, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    meta_title = models.CharField(max_length=200, null=True, blank=True)
    description1 = models.CharField(max_length=500, null=True, blank=True)
    blog_url = models.CharField(max_length=200, unique=True)
    tags = models.CharField(max_length=100, null=True, blank=True)
    author_name = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.blog_title
