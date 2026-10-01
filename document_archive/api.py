from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from .models import Document, Category, Favorite, DocumentView
from .serializers import DocumentSerializer, CategorySerializer, FavoriteSerializer, DocumentViewSerializer

class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Document.objects.all()
        search = self.request.query_params.get('search', None)
        category = self.request.query_params.get('category', None)

        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(author__icontains=search) |
                Q(description__icontains=search) |
                Q(tags__icontains=search) |
                Q(ocr_text__icontains=search)
            )

        if category:
            queryset = queryset.filter(category_id=category)

        return queryset.order_by('-uploaded_at')

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)

    @action(detail=True, methods=['post'])
    def toggle_favorite(self, request, pk=None):
        """Ajouter ou retirer des favoris"""
        document = self.get_object()
        favorite, created = Favorite.objects.get_or_create(
            user=request.user,
            document=document
        )

        if not created:
            favorite.delete()
            return Response({'status': 'removed from favorites'})

        serializer = FavoriteSerializer(favorite)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def view(self, request, pk=None):
        """Enregistrer une consultation"""
        document = self.get_object()
        DocumentView.objects.get_or_create(
            user=request.user,
            document=document
        )
        return Response({'status': 'view recorded'})

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]

class FavoriteViewSet(viewsets.ModelViewSet):
    queryset = Favorite.objects.all()
    serializer_class = FavoriteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user).select_related('document')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class DocumentViewHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DocumentView.objects.all()
    serializer_class = DocumentViewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return DocumentView.objects.filter(user=self.request.user).select_related('document')[:20]
