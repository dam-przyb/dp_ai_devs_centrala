from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("",        include("core.urls")),
    path("01/",     include("lesson_01.urls")),
    path("02/",     include("lesson_02.urls")),
    path("03/",     include("lesson_03.urls")),
    path("04/",     include("lesson_04.urls")),
    path("05/",     include("lesson_05.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
