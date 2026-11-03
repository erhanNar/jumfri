from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import datetime

class Surucu(models.Model):
    ad_soyad = models.CharField(max_length=100, verbose_name="Ad Soyad")
    telefon = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefon Numarası")
    
    # E-posta alanı artık unique=True oldu, böylece get_or_create hatasız çalışır
    eposta = models.EmailField(blank=True, null=True, unique=True, verbose_name="E-Posta Adresi")
    fatura_adresi = models.TextField(blank=True, null=True, verbose_name="Fatura Adresi")
    
    kayit_tarihi = models.DateTimeField(auto_now_add=True, verbose_name="Kayıt Tarihi")

    def __str__(self):
        return f"{self.ad_soyad} ({self.eposta})"


class Analiz(models.Model):
    # Hangi sürücüye ait olduğunu belirten bağ (Foreign Key)
    # Şimdilik mevcut sistemin patlamaması için null=True, blank=True bırakıyoruz
    surucu = models.ForeignKey(Surucu, on_delete=models.CASCADE, related_name='analizler', null=True, blank=True)
    
    giris = models.CharField(max_length=20, verbose_name="Giriş Tarihi")
    cikis = models.CharField(max_length=20, verbose_name="Çıkış Tarihi")
    gun = models.IntegerField(default=0, verbose_name="Gün Sayısı")
    
    # 190 günlük otomatik temizlik ("sil-süpür") için sistem kayıt tarihi
    olusturma_tarihi = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.surucu:
            return f"{self.surucu.ad_soyad} - {self.giris} / {self.cikis}"
        return f"Misafir - {self.giris} / {self.cikis}"



        # --- YENİ EKLEYECEĞİMİZ KULLANICI PROFİL MODELİ ---
class KullaniciProfili(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profil')
    telefon = models.CharField(max_length=20, verbose_name="Telefon Numarası")
    pin_sifre = models.CharField(max_length=128, verbose_name="4 Haneli PIN (Şifreli)")  # Güvenlik için hash'lenecek
    
    # E-posta OTP (Tek Kullanımlık Kod) Doğrulama Alanları
    otp_kod = models.CharField(max_length=6, blank=True, null=True)
    otp_son_kullanma = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.telefon})"

    def otp_gecerli_mi(self, girilen_kod):
        if self.otp_kod == girilen_kod and self.otp_son_kullanma:
            return timezone.now() <= self.otp_son_kullanma
        return False