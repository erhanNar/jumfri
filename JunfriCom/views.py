import random
import re
import pypdf
from datetime import datetime, timedelta
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.models import User
from .models import KullaniciProfili, Surucu, Analiz

def otp_kod_gonder(profil):
    kod = str(random.randint(100000, 999999))
    profil.otp_kod = kod
    profil.save()
    print(f"\n[OTP SİSTEMİ] {profil.user.email} için doğrulama kodu: {kod}\n")
    return kod

def tarih_parse(tarih_str):
    if not tarih_str:
        return None
    tarih_str = str(tarih_str).strip()
    for fmt in ('%d.%m.%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(tarih_str, fmt).date()
        except ValueError:
            continue
    return None

def gun_hesapla_farki(cikis_tarihi, giris_tarihi):
    try:
        d1 = tarih_parse(cikis_tarihi)
        d2 = tarih_parse(giris_tarihi)
        if d1 and d2:
            fark = (d2 - d1).days
            if fark >= 0:
                return fark + 1
            return 0
        return 0
    except Exception:
        return 0

def giris_ve_otp_view(request):
    if request.method == 'POST':
        islem = request.POST.get('islem')
        
        if islem == 'pin_kontrol':
            email = request.POST.get('email', '').strip()
            if not email:
                return JsonResponse({'status': 'hata', 'mesaj': 'Lütfen geçerli bir e-posta adresi girin.'})
            
            try:
                user_obj, _ = User.objects.get_or_create(
                    username=email,
                    defaults={'email': email, 'first_name': 'Kullanıcı'}
                )
                profil, _ = KullaniciProfili.objects.get_or_create(user=user_obj)
                otp_kod_gonder(profil)
                return JsonResponse({'status': 'otp_gonderildi', 'email': email})
            except Exception as e:
                return JsonResponse({'status': 'hata', 'mesaj': f'İşlem sırasında hata oluştu: {str(e)}'})

        elif islem == 'otp_dogrula':
            email = request.POST.get('email', '').strip()
            girilen_kod = request.POST.get('otp_kod', '').strip()
            oturum_secenegi = request.POST.get('oturum_suresi', '1')
            
            try:
                profil = KullaniciProfili.objects.get(user__email=email)
                if profil.otp_kod == girilen_kod:
                    sure_haritasi = {'1': 3600, '4': 14400, '24': 86400}
                    secilen_saniye = sure_haritasi.get(oturum_secenegi, 3600)
                    request.session.set_expiry(secilen_saniye)
                    request.session['kullanici_email'] = email
                    
                    try:
                        surucu, _ = Surucu.objects.get_or_create(
                            eposta=email,
                            defaults={'ad_soyad': profil.user.first_name or 'Kullanıcı'}
                        )
                        request.session['surucu_id'] = surucu.id
                    except Exception:
                        pass
                    
                    return JsonResponse({'status': 'basarili', 'yonlendir': '/hesapla/'})
                else:
                    return JsonResponse({'status': 'hata', 'mesaj': 'Doğrulama kodu geçersiz.'})
            except KullaniciProfili.DoesNotExist:
                return JsonResponse({'status': 'hata', 'mesaj': 'Kullanıcı bulunamadı.'})

    return render(request, 'giris.html')

def hesapla_view(request):
    surucu_id = request.session.get('surucu_id')
    kullanici_email = request.session.get('kullanici_email')
    
    if not surucu_id or not kullanici_email:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.method == 'POST':
            return JsonResponse({'status': 'oturum_bitti', 'yonlendir': '/giris/'})
        return redirect('/giris/')

    if request.method == 'POST':
        islem = request.POST.get('islem')
        
        # 1. Kullanıcı Kaydet
        if islem == 'kullanici_kaydet':
            ad_soyad = request.POST.get('ad_soyad', '').strip()
            telefon = request.POST.get('telefon', '').strip()
            eposta = request.POST.get('email', '').strip()
            
            if not ad_soyad or not eposta:
                return JsonResponse({'status': 'error', 'hata_mesaji': 'Ad Soyad ve E-posta zorunludur.'})

            temiz_tel = telefon[1:] if telefon.startswith('+') else telefon
            telefon_rakamlar = "".join(filter(str.isdigit, temiz_tel))

            gecerli_backend = False
            if telefon.startswith('+90') and len(telefon_rakamlar) == 12 and telefon_rakamlar.startswith('905'):
                gecerli_backend = True
            elif telefon.startswith('05') and len(telefon_rakamlar) == 11:
                gecerli_backend = True

            if not gecerli_backend:
                return JsonResponse({
                    'status': 'error', 
                    'hata_mesaji': 'Lütfen +905... (13 karakter) veya 05... (11 karakter) formatında geçerli bir cep telefonu numarası giriniz.'
                })

            try:
                surucu = Surucu.objects.get(id=surucu_id)
                surucu.ad_soyad = ad_soyad
                surucu.telefon = telefon
                surucu.eposta = eposta
                surucu.save()
            except Surucu.DoesNotExist:
                surucu, _ = Surucu.objects.get_or_create(
                    eposta=eposta, 
                    defaults={'ad_soyad': ad_soyad, 'telefon': telefon}
                )
            
            request.session['surucu_id'] = surucu.id
            request.session['kullanici_email'] = eposta
            return JsonResponse({'status': 'success', 'mesaj': 'Bilgiler başarıyla kaydedildi.'})

        # 2. Belge Yükleme ve Sıkı PDF Format Kontrolü
        elif islem == 'belge_analiz_et':
            belge_dosya = request.FILES.get('belge_dosya')
            if not belge_dosya:
                return JsonResponse({'status': 'error', 'hata_mesaji': 'Dosya yüklenmedi.'})

            dosya_adi = belge_dosya.name.lower()
            if not dosya_adi.endswith('.pdf'):
                return JsonResponse({'status': 'error', 'hata_mesaji': 'Geçersiz Dosya Formatı! Lütfen sadece PDF formatında belge yükleyiniz.'})

            try:
                surucu = Surucu.objects.get(id=surucu_id)
                
                tum_metin = ""
                try:
                    reader = pypdf.PdfReader(belge_dosya)
                    for sayfa in reader.pages:
                        metin = sayfa.extract_text()
                        if metin:
                            tum_metin += metin + "\n"
                except Exception as e:
                    return JsonResponse({'status': 'error', 'hata_mesaji': f'PDF okunamadı: {str(e)}'})

                if not tum_metin.strip():
                    return JsonResponse({'status': 'error', 'hata_mesaji': 'Yüklenen PDF belgesinden metin çıkarılamadı.'})

                bugun_tarih = datetime.now().date()
                pencere_siniri = bugun_tarih - timedelta(days=180)
                
                tarih_deseni = r'(\d{2}[./]\d{2}[./]\d{4})'
                bulunan_tarihler = re.findall(tarih_deseni, tum_metin)
                
                gecerli_tarih_objeleri = []
                eski_tarih_var = False

                for t in bulunan_tarihler:
                    t_temiz = t.replace('/', '.')
                    d_obj = tarih_parse(t_temiz)
                    if d_obj:
                        if d_obj > bugun_tarih:
                            continue
                        
                        if d_obj < pencere_siniri:
                            eski_tarih_var = True
                            continue

                        if {'tarih': t_temiz, 'dt': d_obj} not in gecerli_tarih_objeleri:
                            gecerli_tarih_objeleri.append({'tarih': t_temiz, 'dt': d_obj})

                if eski_tarih_var and not gecerli_tarih_objeleri:
                    return JsonResponse({
                        'status': 'error',
                        'hata_mesaji': 'Geçersiz Belge! Yüklediğiniz belgedeki seyahatler yasal 180 günlük Schengen penceresinin dışındadır (çok eski).'
                    })

                gecerli_tarih_objeleri = sorted(gecerli_tarih_objeleri, key=lambda x: x['dt'])
                tespit_edilen_kayitlar = []

                if len(gecerli_tarih_objeleri) >= 2:
                    for k in range(0, len(gecerli_tarih_objeleri) - 1, 2):
                        t1 = gecerli_tarih_objeleri[k]['tarih']
                        t2 = gecerli_tarih_objeleri[k+1]['tarih']
                        d1 = gecerli_tarih_objeleri[k]['dt']
                        d2 = gecerli_tarih_objeleri[k+1]['dt']
                        
                        if d1 <= d2:
                            tespit_edilen_kayitlar.append({'cikis': t1, 'giris': t2})
                        else:
                            tespit_edilen_kayitlar.append({'cikis': t2, 'giris': t1})

                if not tespit_edilen_kayitlar:
                    return JsonResponse({
                        'status': 'error', 
                        'hata_mesaji': 'Yüklenen belgeden geçerli ve 180 günlük yasal pencere içinde seyahat aralığı çıkarılamadı.'
                    })

                Analiz.objects.filter(surucu=surucu).delete()

                yeni_analiz_listesi = []
                for item in tespit_edilen_kayitlar:
                    gun_sayisi = gun_hesapla_farki(item['cikis'], item['giris'])
                    yeni_obj = Analiz.objects.create(
                        surucu=surucu,
                        cikis=item['cikis'],
                        giris=item['giris'],
                        gun=gun_sayisi
                    )
                    yeni_analiz_listesi.append({
                        'id': yeni_obj.id,
                        'cikis': yeni_obj.cikis,
                        'giris': yeni_obj.giris,
                        'gun': yeni_obj.gun
                    })

                guncel_kayitlar = Analiz.objects.filter(surucu=surucu)
                toplam_gun = sum(k.gun for k in guncel_kayitlar)
                kalan_gun = max(90 - toplam_gun, 0)
                
                en_son_giris_dt = None
                for k in guncel_kayitlar:
                    kt = tarih_parse(k.giris)
                    if kt and (en_son_giris_dt is None or kt > en_son_giris_dt):
                        en_son_giris_dt = kt
                
                hedef_tarih_str = "-"
                if en_son_giris_dt:
                    gelecek_tarih = en_son_giris_dt + timedelta(days=90)
                    hedef_tarih_str = gelecek_tarih.strftime("%d.%m.%Y")

                return JsonResponse({
                    'status': 'success',
                    'yeni_analizler': yeni_analiz_listesi,
                    'toplam_gun': toplam_gun,
                    'kalan_gun': kalan_gun,
                    'hedef_tarih': hedef_tarih_str
                })
            except Surucu.DoesNotExist:
                return JsonResponse({'status': 'error', 'hata_mesaji': 'Şoför kaydı bulunamadı.'})

        # 3. Yeni Satır Ekleme (Manuel)
        elif islem == 'yeni_satir_ekle':
            cikis = request.POST.get('cikis', '')
            giris = request.POST.get('giris', '')
            
            yeni_cikis_dt = tarih_parse(cikis)
            yeni_giris_dt = tarih_parse(giris)
            
            if not yeni_cikis_dt or not yeni_giris_dt:
                return JsonResponse({'status': 'error', 'hata_mesaji': 'Lütfen geçerli tarihler girin (GG.AA.YYYY).'})

            if yeni_cikis_dt > yeni_giris_dt:
                return JsonResponse({'status': 'error', 'hata_mesaji': 'Çıkış tarihi, Giriş tarihinden sonra olamaz!'})

            bugun = datetime.now().date()
            pencere_siniri = bugun - timedelta(days=180)
            if yeni_cikis_dt < pencere_siniri:
                return JsonResponse({
                    'status': 'error',
                    'hata_mesaji': f'Girdiğiniz tarih ({cikis}), yasal 180 günlük Schengen penceresinin dışındadır!'
                })

            try:
                surucu = Surucu.objects.get(id=surucu_id)
                diger_kayitlar = Analiz.objects.filter(surucu=surucu)
                
                for kayit in diger_kayitlar:
                    k_cikis = tarih_parse(kayit.cikis)
                    k_giris = tarih_parse(kayit.giris)
                    if k_cikis and k_giris:
                        if yeni_cikis_dt <= k_giris and yeni_giris_dt >= k_cikis:
                            return JsonResponse({
                                'status': 'error',
                                'hata_mesaji': f'Girdiğiniz tarihler ({kayit.cikis} - {kayit.giris}) seyahat aralığı ile çakışmaktadır!'
                            })

                hesaplanan_gun = gun_hesapla_farki(cikis, giris)
                Analiz.objects.create(surucu=surucu, cikis=cikis, giris=giris, gun=hesaplanan_gun)
                return JsonResponse({'status': 'success'})
            except Surucu.DoesNotExist:
                return JsonResponse({'status': 'error', 'hata_mesaji': 'Şoför kaydı bulunamadı.'})

        # 4. Takvimden Gün Ekleme / Genişletme / Bölünme
        elif islem == 'takvim_gun_ekle':
            tiklanan_str = request.POST.get('cikis', '')
            t_dt = tarih_parse(tiklanan_str)
            
            if not t_dt:
                return JsonResponse({'status': 'error', 'hata_mesaji': 'Geçersiz tarih.'})

            bugun = datetime.now().date()
            pencere_siniri = bugun - timedelta(days=180)
            if t_dt < pencere_siniri:
                return JsonResponse({
                    'status': 'error',
                    'hata_mesaji': f'Girdiğiniz tarih ({tiklanan_str}), yasal 180 günlük Schengen penceresinin dışındadır!'
                })

            try:
                surucu = Surucu.objects.get(id=surucu_id)
                mevcut_kayitlar = Analiz.objects.filter(surucu=surucu)

                bolundu = False
                for kayit in mevcut_kayitlar:
                    kc = tarih_parse(kayit.cikis)
                    kg = tarih_parse(kayit.giris)
                    if kc and kg and kc < t_dt and t_dt < kg:
                        sol_giris_dt = t_dt - timedelta(days=1)
                        sag_cikis_dt = t_dt + timedelta(days=1)
                        
                        kayit.delete()
                        
                        Analiz.objects.create(
                            surucu=surucu,
                            cikis=kc.strftime('%d.%m.%Y'),
                            giris=sol_giris_dt.strftime('%d.%m.%Y'),
                            gun=gun_hesapla_farki(kc.strftime('%d.%m.%Y'), sol_giris_dt.strftime('%d.%m.%Y'))
                        )
                        Analiz.objects.create(
                            surucu=surucu,
                            cikis=sag_cikis_dt.strftime('%d.%m.%Y'),
                            giris=kg.strftime('%d.%m.%Y'),
                            gun=gun_hesapla_farki(sag_cikis_dt.strftime('%d.%m.%Y'), kg.strftime('%d.%m.%Y'))
                        )
                        bolundu = True
                        break
                
                if bolundu:
                    return JsonResponse({'status': 'success'})

                birlesti = False
                for kayit in mevcut_kayitlar:
                    kc = tarih_parse(kayit.cikis)
                    kg = tarih_parse(kayit.giris)
                    if kc and kg:
                        if t_dt == kc - timedelta(days=1):
                            kayit.cikis = t_dt.strftime('%d.%m.%Y')
                            kayit.gun = gun_hesapla_farki(kayit.cikis, kayit.giris)
                            kayit.save()
                            birlesti = True
                            break
                        elif t_dt == kg + timedelta(days=1):
                            kayit.giris = t_dt.strftime('%d.%m.%Y')
                            kayit.gun = gun_hesapla_farki(kayit.cikis, kayit.giris)
                            kayit.save()
                            birlesti = True
                            break

                if birlesti:
                    return JsonResponse({'status': 'success'})

                Analiz.objects.create(
                    surucu=surucu,
                    cikis=tiklanan_str,
                    giris=tiklanan_str,
                    gun=1
                )
                return JsonResponse({'status': 'success'})

            except Surucu.DoesNotExist:
                return JsonResponse({'status': 'error', 'hata_mesaji': 'Şoför bulunamadı.'})

        # 5. Satır Güncelleme
        elif islem == 'satir_guncelle':
            analiz_id = request.POST.get('id')
            cikis = request.POST.get('cikis', '').strip()
            giris = request.POST.get('giris', '').strip()
            
            try:
                analiz = Analiz.objects.get(id=analiz_id)
                
                yeni_cikis_dt = tarih_parse(cikis)
                yeni_giris_dt = tarih_parse(giris)
                
                if not yeni_cikis_dt or not yeni_giris_dt:
                    return JsonResponse({'status': 'error', 'hata_mesaji': 'Geçersiz tarih formatı (GG.AA.YYYY kullanın).'})

                if yeni_cikis_dt > yeni_giris_dt:
                    return JsonResponse({'status': 'error', 'hata_mesaji': 'Çıkış tarihi, Giriş tarihinden sonra olamaz!'})

                bugun = datetime.now().date()
                pencere_siniri = bugun - timedelta(days=180)
                if yeni_cikis_dt < pencere_siniri:
                    return JsonResponse({
                        'status': 'error',
                        'hata_mesaji': f'Girdiğiniz tarih ({cikis}), yasal 180 günlük Schengen penceresinin dışındadır!'
                    })

                diger_kayitlar = Analiz.objects.filter(surucu_id=surucu_id).exclude(id=analiz_id)
                for kayit in diger_kayitlar:
                    k_cikis = tarih_parse(kayit.cikis)
                    k_giris = tarih_parse(kayit.giris)
                    if k_cikis and k_giris:
                        if yeni_cikis_dt <= k_giris and yeni_giris_dt >= k_cikis:
                            return JsonResponse({
                                'status': 'error',
                                'hata_mesaji': f'Girdiğiniz tarihler ({kayit.cikis} - {kayit.giris}) seyahat aralığı ile çakışmaktadır!'
                            })

                analiz.cikis = cikis
                analiz.giris = giris
                analiz.gun = gun_hesapla_farki(cikis, giris)
                analiz.save()
                
                guncel_kayitlar = Analiz.objects.filter(surucu_id=surucu_id)
                toplam_gun = sum(k.gun for k in guncel_kayitlar)
                kalan_gun = max(90 - toplam_gun, 0)
                
                en_son_giris_dt = None
                for k in guncel_kayitlar:
                    kt = tarih_parse(k.giris)
                    if kt and (en_son_giris_dt is None or kt > en_son_giris_dt):
                        en_son_giris_dt = kt
                
                hedef_tarih_str = "-"
                if en_son_giris_dt:
                    gelecek_tarih = en_son_giris_dt + timedelta(days=90)
                    hedef_tarih_str = gelecek_tarih.strftime("%d.%m.%Y")
                
                return JsonResponse({
                    'status': 'success', 
                    'yeni_gun': analiz.gun,
                    'toplam_gun': toplam_gun,
                    'kalan_gun': kalan_gun,
                    'hedef_tarih': hedef_tarih_str
                })
            except Analiz.DoesNotExist:
                return JsonResponse({'status': 'error', 'hata_mesaji': 'Kayıt bulunamadı.'})

        # 6. Satır Silme
        elif islem == 'satir_sil':
            analiz_id = request.POST.get('id')
            try:
                analiz = Analiz.objects.get(id=analiz_id, surucu_id=surucu_id)
                analiz.delete()
                
                guncel_kayitlar = Analiz.objects.filter(surucu_id=surucu_id)
                toplam_gun = sum(k.gun for k in guncel_kayitlar)
                kalan_gun = max(90 - toplam_gun, 0)
                
                en_son_giris_dt = None
                for k in guncel_kayitlar:
                    kt = tarih_parse(k.giris)
                    if kt and (en_son_giris_dt is None or kt > en_son_giris_dt):
                        en_son_giris_dt = kt
                
                hedef_tarih_str = "-"
                if en_son_giris_dt:
                    gelecek_tarih = en_son_giris_dt + timedelta(days=90)
                    hedef_tarih_str = gelecek_tarih.strftime("%d.%m.%Y")
                
                return JsonResponse({
                    'status': 'success',
                    'toplam_gun': toplam_gun,
                    'kalan_gun': kalan_gun,
                    'hedef_tarih': hedef_tarih_str
                })
            except Analiz.DoesNotExist:
                return JsonResponse({'status': 'error', 'hata_mesaji': 'Silinecek kayıt bulunamadı.'})

    aktif_surucu = None
    son_analizler = []
    toplam_gun = 0
    kalan_gun = 90
    hedef_tarih_str = "-"
    
    try:
        aktif_surucu = Surucu.objects.get(id=surucu_id)
        son_analizler = Analiz.objects.filter(surucu=aktif_surucu)
        toplam_gun = sum(k.gun for k in son_analizler)
        kalan_gun = max(90 - toplam_gun, 0)
        
        en_son_giris_dt = None
        for k in son_analizler:
            kt = tarih_parse(k.giris)
            if kt and (en_son_giris_dt is None or kt > en_son_giris_dt):
                en_son_giris_dt = kt
                
        if en_son_giris_dt:
            gelecek_tarih = en_son_giris_dt + timedelta(days=90)
            hedef_tarih_str = gelecek_tarih.strftime("%d.%m.%Y")
    except Surucu.DoesNotExist:
        pass

    context = {
        'surucu': aktif_surucu,
        'son_analizler': son_analizler,
        'toplam_gun': toplam_gun,
        'kalan_gun': kalan_gun,
        'hedef_tarih': hedef_tarih_str
    }
    return render(request, 'hesapla_form.html', context)

def cikis_view(request):
    request.session.flush() 
    return redirect('/giris/')