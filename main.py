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
# KUMANDA GİRİŞİ
OZEL_ISTEK = os.environ.get("OZEL_ISTEK", "")

# Telegram TOPIC ID (Eğer bir alt başlığa atacaksan buraya ID yaz, yoksa None kalsın)
TELEGRAM_TOPIC_ID = None 

if not GOOGLE_API_KEY:
    print("❌ API Key Eksik!")
    exit(1)

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# DOĞRU SEMBOLLER LİSTESİ
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
    # Eğer Topic (Alt Başlık) varsa ona gönder
    if TELEGRAM_TOPIC_ID:
        payload["message_thread_id"] = TELEGRAM_TOPIC_ID

    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram hatası: {e}")

def session_olustur():
    """Yahoo Finance engelini aşmak için sahte tarayıcı oturumu"""
    session = requests.Session()
    ua = UserAgent()
    # Rastgele bir tarayıcı kimliği al
    header = {
        'User-Agent': ua.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }
    session.headers.update(header)
    return session

def veri_analiz_et(sembol):
    try:
        # 1. KAMUFLAJLI OTURUM AÇ
        session = session_olustur()
        
        # 2. Yahoo'dan Veriyi İste (Timeout ekledik ki takılmasın)
        ticker = yf.Ticker(sembol, session=session)
        df = ticker.history(period="1y", interval="1d", timeout=10)
        
        # Engel yedik mi kontrol et
        if df.empty:
            print(f"⚠️ {sembol}: Veri boş geldi (Bloklanmış olabilir)")
            return None

        # --- TEKNİK ANALİZ ---
        son_fiyat = df['Close'].iloc[-1]
        
        # Haftalık Değişim
        haftalik_degisim = 0
        if len(df) > 5:
            haftalik_degisim = ((son_fiyat - df['Close'].iloc[-6]) / df['Close'].iloc[-6]) * 100
            
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
            "haftalik": round(haftalik_degisim, 1)
        }
    except Exception as e:
        print(f"Hata ({sembol}): {e}")
        return None

def raporla():
    # --- ÖZEL İSTEK ---
    if OZEL_ISTEK and len(OZEL_ISTEK) > 1:
        s = OZEL_ISTEK.upper().strip()
        # Otomatik uzantı düzeltme
        if not any(x in s for x in ['.', '=', '-']):
            s += ".IS"
        
        telegrama_yaz(f"🔍 **{s}** İnceleniyor (Kamuflaj Modu)...")
        veri = veri_analiz_et(s)
        
        if veri:
            prompt = f"Finansal analiz: {veri['sembol']}, Fiyat: {veri['fiyat']}, RSI: {veri['rsi']}, Haftalık: %{veri['haftalik']}. Al/Sat/Bekle?"
            ai_cevap = model.generate_content(prompt).text
            
            mesaj = f"📊 **{veri['sembol']} ÖZEL RAPOR**\n"
            mesaj += f"💰 Fiyat: {veri['fiyat']}\n"
            mesaj += f"📈 Haftalık: %{veri['haftalik']}\n"
            mesaj += f"🚦 Sinyal: {veri['sinyal']}\n"
            mesaj += f"💡 _{ai_cevap}_"
            telegrama_yaz(mesaj)
        else:
            telegrama_yaz(f"⚠️ `{s}` verisi çekilemedi. Sembolü kontrol et (Örn: GMSTR.IS)")
        return

    # --- GENEL RAPOR ---
    print("Genel rapor başlıyor...")
    mesaj = f"🇹🇷 **PİYASA RAPORU** ({tr_saati()})\n"
    ham_veri = ""
    basarili_sayisi = 0

    for kategori, semboller in SABIT_LISTE.items():
        mesaj += f"\n*{kategori}*\n"
        for sembol in semboller:
            # Her istek arasına 2 saniye bekleme koy (Robot olmadığımızı kanıtlamak için)
            time.sleep(2) 
            
            veri = veri_analiz_et(sembol)
            if veri:
                basarili_sayisi += 1
                ikon = "🚀" if "🔥" in veri['sinyal'] or "🟢" in veri['sinyal'] else "▪️"
                mesaj += f"{ikon} `{sembol}`: {veri['fiyat']} | {veri['sinyal']}\n"
                ham_veri += f"{sembol}: Fiyat={veri['fiyat']}, Sinyal={veri['sinyal']}, RSI={veri['rsi']}\n"
            else:
                mesaj += f"❌ `{sembol}`: Erişim Engeli\n"

    if basarili_sayisi == 0:
        telegrama_yaz("⚠️ TÜM VERİLER ENGELLENDİ. Yahoo Finance IP bloklaması uyguluyor. 1 saat sonra tekrar deneyecek.")
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
