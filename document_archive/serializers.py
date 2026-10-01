from rest_framework import serializers
from .models import Document, Category, Favorite, DocumentView

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']

class DocumentSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.IntegerField(write_only=True)
    uploaded_by = serializers.StringRelatedField(read_only=True)
    is_favorite = serializers.SerializerMethodField()
    tags_list = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            'id', 'title', 'author', 'description', 'file', 'thumbnail',
            'category', 'category_id', 'tags', 'tags_list', 'uploaded_by',
            'uploaded_at', 'compressed', 'ocr_text', 'is_favorite'
        ]
        read_only_fields = ['uploaded_by', 'uploaded_at', 'thumbnail']

    def get_is_favorite(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Favorite.objects.filter(user=request.user, document=obj).exists()
        return False

    def get_tags_list(self, obj):
        return [tag.strip() for tag in obj.tags.split(',')] if obj.tags else []

class FavoriteSerializer(serializers.ModelSerializer):
    document = DocumentSerializer(read_only=True)
    document_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Favorite
        fields = ['id', 'document', 'document_id', 'added_at']
        read_only_fields = ['added_at']

class DocumentViewSerializer(serializers.ModelSerializer):
    document = DocumentSerializer(read_only=True)

    class Meta:
        model = DocumentView
        fields = ['id', 'document', 'viewed_at']