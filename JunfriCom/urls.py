from django.contrib import admin
from django.urls import path
from .views import giris_ve_otp_view, hesapla_view, cikis_view

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # 1. Ana dizin veya /giris/ isteği gelince giriş fonksiyonunu çalıştır
    path('', giris_ve_otp_view, name='giris_kok'),
    path('giris/', giris_ve_otp_view, name='giris'),
    
    # 2. Hesaplama ve Çıkış sayfaları
    path('hesapla/', hesapla_view, name='hesapla'),
    path('cikis/', cikis_view, name='cikis'), # <-- Çıkış rotası
]