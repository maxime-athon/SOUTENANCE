from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api-auth/', include('rest_framework.urls')),
    path('', include('core.urls')),                     # Authentification + Dashboard
    path('audio/', include('audio_archive.urls')),       # App 1: Audios
    path('documents/', include('document_archive.urls')),# App 2: Documents
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)