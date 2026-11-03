from datetime import datetime, timedelta
from google import genai
from PIL import Image
import sqlite3
import streamlit as st
import time

# ==========================================
# 1. VERİTABANI BAŞLATMA (KALICI VERİ YAPISI)
# ==========================================
def init_db():
  conn = sqlite3.connect("schengen.db")
  cursor = conn.cursor()
  
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            analysis_date TEXT,
            result_text TEXT
        )
    """)
  
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            phone TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            updated_at TEXT
        )
    """)

  # 190 günden eski kayıtları veritabanından otomatik temizle (DB şişmesini önler)
  bugun = datetime.now().date()
  yuz_doksan_gun_once = bugun - timedelta(days=190)
  yuz_doksan_gun_once_str = yuz_doksan_gun_once.strftime("%Y-%m-%d")
  
  try:
    cursor.execute(
        "DELETE FROM analyses WHERE analysis_date < ?", 
        (yuz_doksan_gun_once_str,)
    )
  except Exception as e:
    print(f"Eski kayıt temizleme uyarısı: {e}")

  conn.commit()
  conn.close()

def save_analysis_to_db(first_name, last_name, phone, result_text):
  conn = sqlite3.connect("schengen.db")
  cursor = conn.cursor()
  date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  cursor.execute(
      """
        INSERT INTO analyses (first_name, last_name, phone, analysis_date, result_text) 
        VALUES (?, ?, ?, ?, ?)
    """,
      (first_name, last_name, phone, date_str, result_text),
  )
  conn.commit()
  conn.close()

def save_or_update_user(first_name, last_name, phone):
  if phone and phone != "0555...":
    conn = sqlite3.connect("schengen.db")
    cursor = conn.cursor()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("SELECT phone FROM users WHERE phone = ?", (phone,))
    exists = cursor.fetchone()

    if exists:
      cursor.execute(
          """
            UPDATE users 
            SET first_name = ?, last_name = ?, updated_at = ? 
            WHERE phone = ?
          """,
          (first_name, last_name, date_str, phone),
      )
    else:
      cursor.execute(
          """
            INSERT INTO users (phone, first_name, last_name, updated_at) 
            VALUES (?, ?, ?, ?)
          """,
          (phone, first_name, last_name, date_str),
      )
    
    conn.commit()
    conn.close()

# Veritabanını başlat
init_db()

# ==========================================
# 2. SAYFA YAPILANDIRMASI
# ==========================================
st.set_page_config(
    page_title="Schengen Gün Takip Sistemi",
    page_icon="🇪🇺",
    layout="centered",
)

# ==========================================
# 3. GEMINI API BAĞLANTISI
# ==========================================
API_KEY = "AQ.Ab8RN6J8xIsGY3rfXybEf8xqe-ZHGxTwn9U9usvI9yDbcFtIxQ"

try:
  client = genai.Client(api_key=API_KEY)
  api_ready = True
except Exception as e:
  api_ready = False
  st.error(f"API Bağlantı Hatası: {e}")

# ==========================================
# 4. SESSION STATE BAŞLATMA
# ==========================================
if "phone_input" not in st.session_state:
  conn = sqlite3.connect("schengen.db")
  cursor = conn.cursor()
  cursor.execute("SELECT phone, first_name, last_name FROM users ORDER BY updated_at DESC LIMIT 1")
  last_user = cursor.fetchone()
  conn.close()

  if last_user and last_user[0]:
    st.session_state["phone_input"] = last_user[0]
    st.session_state["first_name_input"] = last_user[1] if last_user[1] else ""
    st.session_state["last_name_input"] = last_user[2] if last_user[2] else ""
  else:
    st.session_state["phone_input"] = ""
    st.session_state["first_name_input"] = ""
    st.session_state["last_name_input"] = ""

# ==========================================
# 5. KULLANICI BİLGİLERİ ALANI (FORM MİMARİSİ)
# ==========================================
st.caption("Schengen sürenizi öğrenin")

current_phone_val = st.session_state.get("phone_input", "").strip()

with st.form("user_profile_form"):
  st.subheader("Kullanıcı Bilgileri")
  
  is_phone_locked = bool(current_phone_val and current_phone_val != "")

  phone_val = st.text_input(
      "Telefon Numaranız", 
      value=st.session_state["phone_input"],
      disabled=is_phone_locked,
      placeholder="0555...",
      help="Telefon numarası bir kez kaydedildikten sonra değiştirilemez."
  )

  fname_val = st.text_input(
      "Adınız", 
      value=st.session_state["first_name_input"],
      placeholder="Adınız..."
  )

  lname_val = st.text_input(
      "Soyadınız", 
      value=st.session_state["last_name_input"],
      placeholder="Soyadınız..."
  )

  profile_submitted = st.form_submit_button("Bilgileri Güncelle / Kaydet")
  
  if profile_submitted:
    digits_chk = "".join(filter(str.isdigit, phone_val))
    if not fname_val or fname_val == "Adınız..." or not lname_val or lname_val == "soyadınız..." or not phone_val:
      st.warning("⚠️ Lütfen tüm alanları doldurun!")
    elif len(digits_chk) < 11:
      st.warning("⚠️ Telefon numarası en az 11 haneli olmalıdır!")
    else:
      st.session_state["phone_input"] = phone_val
      st.session_state["first_name_input"] = fname_val
      st.session_state["last_name_input"] = lname_val
      save_or_update_user(fname_val, lname_val, phone_val)
      st.success("✅ Bilgileriniz başarıyla kaydedildi/güncellendi!")

# ==========================================
# 📌 KAYIT LİSTELE / GÜNCELLE ALANI
# ==========================================
with st.expander("📂 Kayıt Listele/Güncelle"):
  active_phone = st.session_state.get("phone_input", "").strip()
  if not active_phone:
    st.warning("⚠️ Henüz kayıtlı bir telefon numaranız bulunmuyor.")
  else:
    conn = sqlite3.connect("schengen.db")
    cursor = conn.cursor()
    cursor.execute(
        """
          SELECT result_text 
          FROM analyses 
          WHERE phone = ? 
          ORDER BY id DESC
          LIMIT 1
      """,
        (active_phone,),
    )
    row = cursor.fetchone()
    conn.close()

    if row and row[0]:
      st.markdown("### Schengen'de Kalınan Gün")
      clean_text = row[0].replace("### Yurt Dışı Seyahatleri ve Gün Dağılımı Tablosu", "").replace("### Schengen'de Kalınan Gün Toplamı", "").strip()
      
      # --- 180 GÜNLÜK RENKLİ BAR VE TARİH HESABI ---
      import re
      numbers = re.findall(r'\d+', clean_text)
      
      toplam_gun = 0
      if numbers:
        try:
          toplam_gun = int(numbers[-1])
        except:
          toplam_gun = 62
      
      yasal_sinir = 90
      kullanilan = min(toplam_gun, yasal_sinir)
      kalan = max(0, yasal_sinir - kullanilan)
      oran = min(1.0, kullanilan / yasal_sinir)

      date_pattern = r'\d{2}/\d{2}/\d{4}'
      all_dates = re.findall(date_pattern, clean_text)
      
      son_giris_str = "Belirtilmemiş"
      if all_dates and len(all_dates) >= 2:
        son_giris_str = all_dates[-1]
        try:
          son_giris_dt = datetime.strptime(son_giris_str, "%d/%m/%Y")
          doksen_gun_sonra = son_giris_dt + timedelta(days=90)
          gelecek_tarih_str = doksen_gun_sonra.strftime("%d/%m/%Y")
        except:
          gelecek_tarih_str = "Hesaplanamadı"
      else:
        gelecek_tarih_str = "Bilinmiyor"

      lines = [line.strip() for line in clean_text.split('\n') if '|' in line]
      
      table_rows_html = ""
      col_count = 4 
      
      for i, line in enumerate(lines):
        if '---' in line:
          continue
        
        cols = [c.strip().replace('**', '') for c in line.split('|')[1:-1]]
        if not cols:
          continue
        
        if i == 0:
          col_count = len(cols)
          th_s = "".join([f"<th style='border: 1px solid #e0e0e0; padding: 8px; background-color: #f8f9fa; text-align: center; color: #31333F;'>{c}</th>" for c in cols])
          table_rows_html += f"<thead><tr>{th_s}</tr></thead><tbody>"
        else:
          is_total = "TOPLAM" in cols[0].upper() or "TOPLAM" in line.upper()
          bg_color = "#f8f9fa" if is_total else "#ffffff"
          font_weight = "bold" if is_total else "normal"
          
          td_s = "".join([f"<td style='border: 1px solid #e0e0e0; padding: 8px; text-align: center; font-weight: {font_weight}; background-color: {bg_color}; color: #31333F;'>{c}</td>" for c in cols])
          table_rows_html += f"<tr>{td_s}</tr>"
      
      table_rows_html += "</tbody>"

      bar_row_html = f"""
      <tbody>
        <tr>
          <td colspan="{col_count}" style="border: 1px solid #e0e0e0; border-bottom: none; padding: 10px; background-color: #ffffff; text-align: center;">
            <div style="width: 100%; background-color: #2ecc71; border-radius: 6px; overflow: hidden; height: 26px; display: flex;">
              <div style="width: {oran * 100}%; background-color: #e74c3c; height: 100%; text-align: center; color: white; font-weight: bold; line-height: 26px; font-size: 13px; white-space: nowrap;">
                {kullanilan} Gün Kullanıldı
              </div>
              <div style="width: {(1 - oran) * 100}%; background-color: #2ecc71; height: 100%; text-align: center; color: white; font-weight: bold; line-height: 26px; font-size: 13px; white-space: nowrap;">
                {kalan} Gün Kalan
              </div>
            </div>
          </td>
        </tr>
      """

      info_row_html = f"""
        <tr>
          <td colspan="{col_count}" style="border: 1px solid #e0e0e0; border-top: none; padding: 12px; background-color: #f8f9fa; text-align: center; font-size: 13px; color: #31333F;">
            📅 <span style="color: #e74c3c; font-weight: bold; font-size: 15px;">{gelecek_tarih_str}</span> <span style="color: #000000; font-weight: bold;">tarihinden sonra 90 gün kalabilirsiniz.</span>
          </td>
        </tr>
      </tbody>
      """

      full_table_html = f"""
      <table style="width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 14px; margin-top: 10px;">
        {table_rows_html}
        {bar_row_html}
        {info_row_html}
      </table>
      """
      st.markdown(full_table_html, unsafe_allow_html=True)

    else:
      st.info("Henüz kayıtlı bir analiziniz bulunmuyor.")

# ==========================================
# 6. DİKKAT UYARISI VE İŞLEM SEÇENEKLERİ
# ==========================================
st.markdown("<p style='color:red; font-weight:bold;'>DİKKAT<br>SCHENGENDEN BAŞKA ÜLKEYE ÇIKIŞ VE GİRİŞ YAPANLAR MANUEL GİRİŞİ KULLANMALIDIR.</p>", unsafe_allow_html=True)
st.write("Not : E-devlet belgesi sadece yurttan çıkış ve giriş tarihlerini gösterir Schengen dışı ülkeye girip çıktıysanız BELGE ANALİZİ yanıltıcı olur.")

st.markdown("")

tab1, tab2 = st.tabs(["📄 Belge Analizi", "✍️ Manuel Tarih Girişi"])

# --- TAB 1: BELGE ANALİZİ ---
with tab1:
  with st.form("belge_analiz_form"):
    uploaded_files = st.file_uploader(
        "e-Devlet Belgelerini Yükleyin (Birden fazla seçebilirsiniz)",
        type=["png", "jpg", "jpeg", "pdf"],
        accept_multiple_files=True,
        key="belge_yukleme"
    )

    submitted_analiz = st.form_submit_button("Belgeyi Analiz Et ve Kaydet")

    if submitted_analiz:
      f_name = st.session_state.get("first_name_input", "").strip()
      l_name = st.session_state.get("last_name_input", "").strip()
      phn = st.session_state.get("phone_input", "").strip()
      digits_only = "".join(filter(str.isdigit, phn))

      if not f_name or f_name == "Adınız..." or not l_name or not phn:
        st.warning("⚠️ Lütfen önce yukarıdaki **Kullanıcı Bilgileri** alanını doldurun!")
      elif len(digits_only) < 11:
        st.warning("⚠️ Geçerli bir telefon numarası gereklidir (en az 11 hane).")
      elif not uploaded_files:
        st.warning("⚠️ Lütfen en az bir e-Devlet belgesi yükleyin!")
      elif not api_ready:
        st.error("API yapılandırılmadığı için analiz gerçekleştirilemiyor.")
      else:
        success = False
        analysis_result = ""
        
        bugun_str = datetime.now().strftime("%Y-%m-%d")
        yuz_doksan_gun_once = (datetime.now() - timedelta(days=190)).strftime("%Y-%m-%d")

       # - Başlangıç: Model ve Hata Yönetimi Güncellemesi
        success = False
        analysis_result = ""
        
        for attempt in range(3):
          try:
            with st.spinner(f"Belgeler taranıyor (Deneme {attempt+1}/3)..."):
              contents_list = []
              
              for uploaded_file in uploaded_files:
                if uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
                  image = Image.open(uploaded_file)
                  contents_list.append(image)
                elif uploaded_file.type == "application/pdf":
                  pdf_bytes = uploaded_file.getvalue()
                  contents_list.append({
                      "mime_type": "application/pdf",
                      "data": pdf_bytes
                  })

              prompt_text = (
                  f"Bu e-Devlet belgelerindeki uluslararası giriş ve çıkış tarihlerini kronolojik olarak analiz et. "
                  f"ÖNEMLİ KURAL 1: Belgelerdeki tarihleri giriş ve çıkış günlerini Schengen bölgesine ekleyerek toplam günü hesapla. Giriş yapılan gün de, çıkış yapılan gün de Schengen bölgesinde geçirilmiş tam bir gün sayılacaktır. "
                  f"ÖNEMLİ KURAL 2: Sadece {yuz_doksan_gun_once} ile {bugun_str} tarihleri arasındaki seyahatleri dikkate al. Bu tarihten daha eski kayıtları kesinlikle alma. "
                  f"ASLA HİÇBİR AÇIKLAMA, NOT, YORUM, BAŞLIK VEYA GİRİŞ CÜMLESİ YAZMA. "
                  f"Sadece doğrudan şu 4 sütunu içeren Markdown tablosunu ver:\n"
                  f"| # | Çıkış | Giriş | Gün |\n"
                  f"|---|---|---|---|\n"
                  f"Tarihlerde saat detaylarına kesinlikle yer verme, sadece gün/ay/yıl olarak yaz. "
                  f"En alta da toplam gün satırını ekle. Tablodan başka tek bir kelime bile yazma."
              )
              contents_list.append(prompt_text)

              # Doğru ve geçerli model adını kullanıyoruz
              response = client.models.generate_content(
                  model="gemini-3.8-flash", contents=contents_list
              )
              
              analysis_result = response.text
              success = True
              break
          except Exception as e:
            print(f"API Hatası (Deneme {attempt+1}): {e}")
            if attempt == 2:  
              pass
            else:
              # Sunucu yoğunluğunun dağılması için bekleme süresini 4 saniyeye çıkarıyoruz
              time.sleep(4)

        if success:
          save_analysis_to_db(f_name, l_name, phn, analysis_result)
          st.success("Analiz Başarıyla Tamamlandı ve Kaydedildi!")
          st.markdown("### Schengen'de Kalınan Gün")
          st.markdown(analysis_result.replace("### Yurt Dışı Seyahatleri ve Gün Dağılımı Tablosu", "").replace("### Schengen'de Kalınan Gün Toplamı", "").strip())
        else:
          st.error("⚠️ Sunucularda geçici bir yoğunluk var. Lütfen 10-15 saniye bekleyip tekrar deneyin.")
# - Bitiş: Model ve Hata Yönetimi Güncellemesi