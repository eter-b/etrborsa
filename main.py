import os
import requests
import yfinance as yf
import pandas_ta as ta
import google.generativeai as genai
from datetime import datetime
import pytz # Saat dilimi için

# --- ŞİFRE KONTROL ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
OZEL_ISTEK = os.environ.get("OZEL_ISTEK", "")

if not GOOGLE_API_KEY:
    print("❌ HATA: API Key yok!")
    exit(1)

# --- AYARLAR ---
# İsteğin üzerine FLASH model (Hızlı ve Zeki)
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

SABIT_LISTE = {
    "🛡️ DEFANSİF": ["GC=F", "SI=F", "KCHOL.IS", "SAHOL.IS"], 
    "📈 BÜYÜME": ["THYAO.IS", "ASELS.IS", "TUPRS.IS"], 
    "🚀 RİSKLİ": ["BTC-USD", "ETH-USD", "SOL-USD"] 
}

def tr_saati():
    tz = pytz.timezone('Europe/Istanbul')
    return datetime.now(tz).strftime('%H:%M')

def telegrama_yaz(mesaj):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def veri_analiz_et(sembol):
    try:
        # Veri çekerken hata olursa program durmasın
        ticker = yf.Ticker(sembol)
        df = ticker.history(period="6mo", interval="1d")
        
        if df.empty: 
            print(f"⚠️ {sembol} verisi boş geldi.")
            return None

        # --- İNDİKATÖRLER (Oracle Gözü) ---
        # 1. RSI
        df['RSI'] = ta.rsi(df['Close'], length=14)
        
        # 2. Bollinger Bantları (Patlama Yakalayıcı)
        bb = ta.bbands(df['Close'], length=20, std=2)
        df['BB_UP'] = bb['BBU_20_2.0']
        df['BB_LOW'] = bb['BBL_20_2.0']
        
        # 3. MACD (Trend Dönüşü)
        macd = ta.macd(df['Close'])
        df['MACD'] = macd['MACD_12_26_9']
        df['MACD_SIGNAL'] = macd['MACDs_12_26_9']
        
        # 4. SMA (Ortalama)
        df['SMA20'] = ta.sma(df['Close'], length=20)

        son = df.iloc[-1]
        
        # Sinyal Üretimi
        sinyal = "NÖTR ⚪"
        detay = "Yatay Seyir"
        
        # Bollinger Patlaması
        if son['Close'] > son['BB_UP']: 
            sinyal = "PATLAMA (YUKARI) 🔥"
            detay = "Fiyat üst bandı deldi, sert yükseliş ihtimali."
        elif son['Close'] < son['BB_LOW']: 
            sinyal = "ÇÖKÜŞ (AŞAĞI) ❄️"
            detay = "Fiyat alt bandı deldi, sert düşüş ihtimali."
            
        # RSI Aşırılıkları
        elif son['RSI'] < 30: 
            sinyal = "AŞIRI UCUZ (DİP) 🟢"
            detay = "RSI dipte, tepki alımı gelebilir."
        elif son['RSI'] > 75: 
            sinyal = "AŞIRI PAHALI (TEPE) 🔴"
            detay = "RSI tepede, kar satışı gelebilir."
            
        # MACD Durumu
        macd_yon = "POZİTİF" if son['MACD'] > son['MACD_SIGNAL'] else "NEGATİF"

        return {
            "sembol": sembol,
            "fiyat": round(son['Close'], 2),
            "sinyal": sinyal,
            "rsi": round(son['RSI'], 1),
            "macd": macd_yon,
            "detay": detay,
            "sma20": round(son['SMA20'], 2)
        }
    except Exception as e:
        print(f"Hata ({sembol}): {e}")
        return None

def raporla():
    # ÖZEL İSTEK VARSA
    if OZEL_ISTEK and len(OZEL_ISTEK) > 1:
        telegrama_yaz(f"🔍 **{OZEL_ISTEK}** analizi hazırlanıyor...")
        veri = veri_analiz_et(OZEL_ISTEK)
        if veri:
            prompt = f"Finans uzmanı olarak yorumla: {veri['sembol']}, Fiyat:{veri['fiyat']}, Sinyal:{veri['sinyal']}, Detay:{veri['detay']}. Al/Sat/Tut?"
            ai_cevap = model.generate_content(prompt).text
            telegrama_yaz(f"📊 **{veri['sembol']}**\nFiyat: {veri['fiyat']}\nSinyal: {veri['sinyal']}\n💡 _{ai_cevap}_")
        else:
            telegrama_yaz("⚠️ Veri alınamadı.")
        return

    # GENEL RAPOR
    print("Rapor hazırlanıyor...")
    
    ham_veri_gemini = ""
    tarih = tr_saati()
    mesaj = f"🇹🇷 **PİYASA STRATEJİ RAPORU** ({tarih})\n"
    mesaj += "───────────────────────\n"
    
    veri_var_mi = False

    for kategori, semboller in SABIT_LISTE.items():
        mesaj += f"\n*{kategori}*\n"
        ham_veri_gemini += f"\n--- {kategori} ---\n"
        
        for sembol in semboller:
            veri = veri_analiz_et(sembol)
            if veri:
                veri_var_mi = True
                # Telegram'a kısa özet
                ikon = "▪️"
                if "🔥" in veri['sinyal'] or "🟢" in veri['sinyal']: ikon = "🚀"
                elif "❄️" in veri['sinyal'] or "🔴" in veri['sinyal']: ikon = "⚠️"
                
                mesaj += f"{ikon} `{sembol}`: {veri['fiyat']} | {veri['sinyal']}\n"
                
                # Gemini'ye gidecek DETAYLI teknik veri
                ham_veri_gemini += f"VARLIK: {sembol} | FİYAT: {veri['fiyat']} | RSI: {veri['rsi']} | MACD: {veri['macd']} | SMA20 Durumu: {veri['fiyat'] > veri['sma20']} | SİNYAL: {veri['sinyal']} ({veri['detay']})\n"
            else:
                mesaj += f"❌ `{sembol}`: Veri Yok\n"

    if not veri_var_mi:
        telegrama_yaz("⚠️ Hiçbir veri çekilemedi. Yahoo Finance sunucularında geçici sorun olabilir.")
        return

    # --- GEMINI STRATEJİ ÜRETİMİ ---
    prompt = f"""
    Sen uzman bir Fon Yöneticisisin. Aşağıdaki teknik verileri kullanarak DETAYLI bir strateji raporu yaz.
    
    TEKNİK VERİLER:
    {ham_veri_gemini}
    
    GÖREVİN:
    Aşağıdaki 3 başlık altında, laf kalabalığı yapmadan NET stratejiler belirle.
    Her kategori için "Vade Önerisi" (Kısa/Orta/Uzun) ve "Aksiyon" (Al/Sat/Bekle) ver.
    
    1. 🛡️ DEFANSİF STRATEJİ (Altın, Gümüş, Holdingler):
       - Güvenli liman mı? Yoksa nakite mi dönmeli?
       - Özellikle GÜMÜŞ ve ALTIN için Bollinger/MACD sinyali ne diyor?
    
    2. 📈 BÜYÜME STRATEJİSİ (Hisseler):
       - Trend yukarı mı? Düzeltme riski var mı?
    
    3. 🚀 RİSKLİ PORTFÖY (Kripto):
       - Dip avcılığı zamanı mı?
       
    Üslup: Profesyonel, yatırımcı dostu ve net.
    """
    
    try:
        ai_yorum = model.generate_content(prompt).text
        mesaj += "\n───────────────────────\n"
        mesaj += ai_yorum
    except Exception as e:
        mesaj += f"\n⚠️ Yorum oluşturulamadı: {e}"

    # SÖZLÜK
    mesaj += "\n───────────────────────\n"
    mesaj += "🔥: Patlama (Güçlü Al) | ❄️: Çöküş (Güçlü Sat)\n"
    mesaj += "🟢: Dip (Topla) | 🔴: Zirve (Sat)"
    
    telegrama_yaz(mesaj)
    print("✅ Rapor gönderildi.")

if __name__ == "__main__":
    raporla()
