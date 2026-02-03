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

# TOPIC ID (Varsa yaz, yoksa None)
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
    if TELEGRAM_TOPIC_ID:
        payload["message_thread_id"] = TELEGRAM_TOPIC_ID

    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram hatası: {e}")

def veri_cek_hayalet_mod(sembol):
    """Yahoo Engelini Aşmak İçin Hafifletilmiş İstek"""
    ua = UserAgent()
    
    # 3 Kez Dene
    for i in range(3):
        try:
            session = requests.Session()
            header = {
                'User-Agent': ua.random, # Her seferinde kimlik değiştir
                'Accept': '*/*',
                'Connection': 'keep-alive'
            }
            session.headers.update(header)
            
            # DİKKAT: period="1mo" yaptık. Daha az veri = Daha az dikkat.
            ticker = yf.Ticker(sembol, session=session)
            df = ticker.history(period="1mo", interval="1d", timeout=20)
            
            if not df.empty:
                return df
            
            print(f"⚠️ {sembol} boş geldi. Bekleniyor...")
            time.sleep(random.uniform(3, 7)) # 3 ile 7 saniye arası bekle
            
        except Exception as e:
            print(f"Hata: {e}")
            time.sleep(2)
            
    return None

def teknik_analiz(sembol, df):
    try:
        son_fiyat = df['Close'].iloc[-1]
        
        # Haftalık Değişim (Son 5 gün)
        haftalik = 0
        if len(df) > 5:
            haftalik = ((son_fiyat - df['Close'].iloc[-6]) / df['Close'].iloc[-6]) * 100
            
        # İndikatörler
        df['RSI'] = ta.rsi(df['Close'], length=14)
        bb = ta.bbands(df['Close'], length=20, std=2)
        
        # Son veriler
        rsi = df['RSI'].iloc[-1]
        bb_up = bb['BBU_20_2.0'].iloc[-1]
        bb_low = bb['BBL_20_2.0'].iloc[-1]
        
        # Sinyal Mantığı
        sinyal = "NÖTR ⚪"
        if son_fiyat > bb_up: sinyal = "PATLAMA (YUKARI) 🔥"
        elif son_fiyat < bb_low: sinyal = "DİP KIRILIMI ❄️"
        elif rsi < 30: sinyal = "DİP FIRSATI 🟢"
        elif rsi > 70: sinyal = "ZİRVE RİSKİ 🔴"

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
    # --- ÖZEL İSTEK (KUMANDA) ---
    if OZEL_ISTEK and len(OZEL_ISTEK) > 1:
        s = OZEL_ISTEK.upper().strip()
        # Otomatik Düzeltme
        if not any(x in s for x in ['.', '=', '-']):
            s += ".IS"
        
        telegrama_yaz(f"🔍 **{s}** İnceleniyor (Hayalet Mod)...")
        
        df = veri_cek_hayalet_mod(s)
        if df is not None:
            veri = teknik_analiz(s, df)
            
            # Gemini Yorumu
            prompt = f"Hisse: {veri['sembol']}, Fiyat: {veri['fiyat']}, RSI: {veri['rsi']}, Sinyal: {veri['sinyal']}. Al/Sat/Bekle?"
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
            telegrama_yaz(f"⚠️ `{s}` verisi alınamadı. Kod hatalı olabilir veya piyasa kapalı.")
        return

    # --- GENEL RAPOR ---
    print("Genel rapor başlıyor...")
    mesaj = f"🇹🇷 **PİYASA RAPORU** ({tr_saati()})\n"
    ham_veri = ""
    basarili_sayisi = 0

    for kategori, semboller in SABIT_LISTE.items():
        mesaj += f"\n*{kategori}*\n"
        for sembol in semboller:
            # Her hisse arasında 4 saniye bekle (Bloklanmamak için şart)
            time.sleep(4)
            
            df = veri_cek_hayalet_mod(sembol)
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
        telegrama_yaz("⚠️ Yahoo Finance sunucuları şu an GitHub IP'lerini engelliyor. Daha sonra tekrar denenecek.")
        return

    # Gemini Yorumu
    prompt = f"""
    Sen portföy yöneticisisin. Veriler:
    {ham_veri}
    
    GÖREV:
    Tek bir paragrafta piyasanın genel yönünü ve en büyük fırsatı (RSI < 30 olan veya Patlama yapan) yaz.
    """
    try:
        ai_yorum = model.generate_content(prompt).text
        mesaj += "\n────────────────\n"
        mesaj += ai_yorum
    except: pass

    telegrama_yaz(mesaj)

if __name__ == "__main__":
    raporla()
