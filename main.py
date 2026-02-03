import os
import requests
import yfinance as yf
import pandas_ta as ta
import google.generativeai as genai
from datetime import datetime
import pytz
import time
import random
from fake_useragent import UserAgent

# --- ŞİFRELER ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
OZEL_ISTEK = os.environ.get("OZEL_ISTEK", "")

# BURAYA DİKKAT: Eğer bir grubun alt başlığına atacaksan ID'yi buraya yaz (Sayı olarak).
# Yoksa None olarak kalsın. Örn: TELEGRAM_TOPIC_ID = 2
TELEGRAM_TOPIC_ID = None 

if not GOOGLE_API_KEY:
    print("❌ API Key Eksik! Settings > Secrets kontrol et.")
    exit(1)

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# LİSTE
SABIT_LISTE = {
    "🛡️ DEFANSİF": ["GC=F", "SI=F", "KCHOL.IS", "SAHOL.IS"], 
    "📈 BÜYÜME": ["THYAO.IS", "ASELS.IS", "TUPRS.IS", "GMSTR.IS"], 
    "🚀 RİSKLİ": ["BTC-USD", "ETH-USD", "SOL-USD"] 
}

def tr_saati():
    tz = pytz.timezone('Europe/Istanbul')
    return datetime.now(tz).strftime('%d.%m %H:%M')

def telegrama_yaz(mesaj):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, 
        "text": mesaj, 
        "parse_mode": "Markdown"
    }
    # Eğer Topic ID varsa ekle
    if TELEGRAM_TOPIC_ID:
        payload["message_thread_id"] = TELEGRAM_TOPIC_ID

    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram hatası: {e}")

def veri_cek(sembol, deneme_sayisi=3):
    """Israrcı Veri Çekme Fonksiyonu"""
    ua = UserAgent()
    
    for i in range(deneme_sayisi):
        try:
            # Her denemede farklı bir tarayıcı gibi davran
            session = requests.Session()
            header = {
                'User-Agent': ua.random,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Referer': 'https://www.google.com/'
            }
            session.headers.update(header)
            
            ticker = yf.Ticker(sembol, session=session)
            # 1 yıllık veri iste
            df = ticker.history(period="1y", interval="1d", timeout=15)
            
            if not df.empty:
                return df # Veri geldiyse döndür
            
            print(f"⚠️ {sembol} boş geldi. Tekrar deneniyor ({i+1}/{deneme_sayisi})...")
            time.sleep(random.uniform(2, 5)) # Biraz bekle (Dikkat çekmemek için)
            
        except Exception as e:
            print(f"Hata ({sembol}): {e}")
            time.sleep(2)
    
    return None # Tüm denemeler başarısızsa boş dön

def teknik_analiz(sembol, df):
    try:
        son_fiyat = df['Close'].iloc[-1]
        
        # Haftalık Değişim
        haftalik = 0
        if len(df) > 5:
            haftalik = ((son_fiyat - df['Close'].iloc[-6]) / df['Close'].iloc[-6]) * 100
            
        # İndikatörler
        df['RSI'] = ta.rsi(df['Close'], length=14)
        bb = ta.bbands(df['Close'], length=20, std=2)
        
        rsi = df['RSI'].iloc[-1]
        bb_up = bb['BBU_20_2.0'].iloc[-1]
        bb_low = bb['BBL_20_2.0'].iloc[-1]
        
        # Sinyal Mantığı
        sinyal = "NÖTR ⚪"
        if son_fiyat > bb_up: sinyal = "PATLAMA (YUKARI) 🔥"
        elif son_fiyat < bb_low: sinyal = "DİP KIRILIMI ❄️"
        elif rsi < 30: sinyal = "DİP FIRSATI 🟢"
        elif rsi > 75: sinyal = "ZİRVE RİSKİ 🔴"

        return {
            "sembol": sembol,
            "fiyat": round(son_fiyat, 2),
            "sinyal": sinyal,
            "rsi": round(rsi, 1),
            "haftalik": round(haftalik, 1)
        }
    except:
        return None

def raporla():
    # --- ÖZEL İSTEK (TELEFON KUMANDASI) ---
    if OZEL_ISTEK and len(OZEL_ISTEK) > 1:
        s = OZEL_ISTEK.upper().strip()
        # Otomatik uzantı düzeltme
        if not any(x in s for x in ['.', '=', '-']):
            s += ".IS"
        
        telegrama_yaz(f"🔍 **{s}** İnceleniyor (Israrcı Mod)...")
        
        df = veri_cek(s)
        if df is not None:
            veri = teknik_analiz(s, df)
            prompt = f"Finansal analiz: {veri['sembol']}, Fiyat: {veri['fiyat']}, RSI: {veri['rsi']}, Haftalık: %{veri['haftalik']}. Al/Sat/Bekle?"
            try:
                ai_cevap = model.generate_content(prompt).text
            except:
                ai_cevap = "Yorum alınamadı."
            
            mesaj = f"📊 **{veri['sembol']} ÖZEL RAPOR**\n"
            mesaj += f"💰 Fiyat: {veri['fiyat']}\n"
            mesaj += f"📈 Haftalık: %{veri['haftalik']}\n"
            mesaj += f"🚦 Sinyal: {veri['sinyal']}\n"
            mesaj += f"💡 _{ai_cevap}_"
            telegrama_yaz(mesaj)
        else:
            telegrama_yaz(f"⚠️ `{s}` verisi 3 denemeye rağmen çekilemedi. Yahoo Finance çok yoğun.")
        return

    # --- GENEL RAPOR ---
    print("Genel rapor başlıyor...")
    mesaj = f"🇹🇷 **PİYASA RAPORU** ({tr_saati()})\n"
    ham_veri = ""
    basarili_sayisi = 0

    for kategori, semboller in SABIT_LISTE.items():
        mesaj += f"\n*{kategori}*\n"
        for sembol in semboller:
            df = veri_cek(sembol)
            
            if df is not None:
                veri = teknik_analiz(sembol, df)
                if veri:
                    basarili_sayisi += 1
                    ikon = "🚀" if "🔥" in veri['sinyal'] or "🟢" in veri['sinyal'] else "▪️"
                    mesaj += f"{ikon} `{sembol}`: {veri['fiyat']} | {veri['sinyal']}\n"
                    ham_veri += f"{sembol}: Fiyat={veri['fiyat']}, Sinyal={veri['sinyal']}, RSI={veri['rsi']}\n"
            else:
                mesaj += f"❌ `{sembol}`: Erişim Yok\n"

    if basarili_sayisi == 0:
        telegrama_yaz("⚠️ Yahoo Finance tüm bağlantıları reddetti. 1 saat sonra tekrar deneyecek.")
        return

    # Gemini Yorumu
    prompt = f"""
    Sen portföy yöneticisisin. Veriler:
    {ham_veri}
    
    GÖREV:
    Tek bir paragrafta piyasanın genel yönünü ve en büyük fırsatı (RSI < 30 olan veya Patlama yapan) yaz.
    Yatırım tavsiyesi olmadığını belirt.
    """
    try:
        ai_yorum = model.generate_content(prompt).text
        mesaj += "\n────────────────\n"
        mesaj += ai_yorum
    except: pass

    telegrama_yaz(mesaj)

if __name__ == "__main__":
    raporla()
