<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Dinamik Satır Hesapla Sayfası</title>
    <style>
        body { font-family: sans-serif; margin: 40px; background: #f4f7f6; }
        .row-box { background: #fff; padding: 15px; margin-bottom: 10px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); display: flex; gap: 10px; align-items: center; }
        input { padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
        button { padding: 8px 15px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #218838; }
        .status { font-size: 14px; margin-left: 10px; color: #666; }
    </style>
</head>
<body>

    <h2>Schengen Satır Güncelleme Hesapla Ekranı</h2>

    <!-- ########################################## -->
    <!-- # BAŞLA: DİNAMİK FORM ÇOĞALTMA DÖNGÜSÜ     -->
    <!-- ########################################## -->
    
    <!-- Django tarafında veritabanından gelen verilerle baştan sona doğal dönen döngü -->
    {% for kayit in kayitlar %}
    <form id="F{{ forloop.counter }}" class="row-box" onsubmit="kaydet(event, 'F{{ forloop.counter }}')">
        
        <!-- Veritabanı ID'sini ve döngü sırasını tire ile birleştiriyoruz (örn: id-1, id-2...) -->
        <input type="hidden" name="id-{{ forloop.counter }}" value="{{ kayit.id }}">
        
        <span>Satır {{ forloop.counter }}:</span>
        <label>Çıkış:</label>
        <input type="text" name="cikis{{ forloop.counter }}" value="{{ kayit.cikis }}">
        
        <label>Giriş:</label>
        <input type="text" name="giris{{ forloop.counter }}" value="{{ kayit.giris }}">
        
        <label>Gün:</label>
        <input type="text" name="gun{{ forloop.counter }}" value="{{ kayit.gun }}">
        
        <button type="submit">Kaydet</button>
        <span class="status" id="status-F{{ forloop.counter }}"></span>
    </form>
    {% endfor %}

    <!-- ########################################## -->
    <!-- # BİTİR: DİNAMİK FORM ÇOĞALTMA DÖNGÜSÜ    -->
    <!-- ########################################## -->


    <!-- ########################################## -->
    <!-- # BAŞLA: AJAX & JAVASCRIPT İLETİŞİM BLOKU   -->
    <!-- ########################################## -->
    <script>
        function kaydet(event, formId) {
            event.preventDefault(); // Sayfanın yenilenmesini engelliyoruz
            
            const form = document.getElementById(formId);
            const formData = new FormData(form);
            const statusSpan = document.getElementById('status-' + formId);

            statusSpan.style.color = "#007bff";
            statusSpan.innerText = "Kaydediliyor...";

            // AJAX (Fetch API) ile veriyi Django view'a gönderiyoruz
            fetch('/Hesapla-kaydet-view/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': 'buraya_django_csrf_token_gelecek' 
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    statusSpan.style.color = "green";
                    statusSpan.innerText = "✓ Kaydedildi!";
                } else {
                    statusSpan.style.color = "red";
                    statusSpan.innerText = "Hata oluştu!";
                }
            })
            .catch(error => {
                statusSpan.style.color = "red";
                statusSpan.innerText = "Bağlantı hatası!";
            });
        }
    </script>
    <!-- ########################################## -->
    <!-- # BİTİR: AJAX & JAVASCRIPT İLETİŞİM BLOKU   -->
    <!-- ########################################## -->

</body>
</html>