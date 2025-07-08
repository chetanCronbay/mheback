from rest_framework import serializers
from banners.models import Banner


class BannerSerializer(serializers.ModelSerializer):
    """
    Serializer for the Banner model.
    Simple serializer because the model has only one field.
    """

    class Meta:
        model = Banner
        # Serialize all fields; here it's just 'id' and 'banner' (the image or file path).
        fields = '__all__'