import os
import requests
import yfinance as yf
import pandas_ta as ta
import google.generativeai as genai
from datetime import datetime

# --- ŞİFRE KONTROLÜ (ÇÖKMEYİ ENGELLEYEN KISIM) ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
OZEL_ISTEK = os.environ.get("OZEL_ISTEK", "")

# Eğer şifreler teknik olarak yoksa (Hizalama hatası varsa) uyar
if not GOOGLE_API_KEY:
    print("❌ HATA: GOOGLE_API_KEY Python'a ulaşmadı! main.yml dosyasındaki 'env' hizalamasını kontrol et.")
    exit(1)
if not TELEGRAM_BOT_TOKEN:
    print("❌ HATA: TELEGRAM_BOT_TOKEN eksik.")
    exit(1)

# --- AYARLAR ---
SABIT_LISTE = {
    "🛡️ DEFANSİF": ["GC=F", "SI=F", "KCHOL.IS", "SAHOL.IS"], 
    "📈 BÜYÜME": ["THYAO.IS", "ASELS.IS", "TUPRS.IS"], 
    "🚀 RİSKLİ": ["BTC-USD", "ETH-USD"] 
}

try:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")
except Exception as e:
    print(f"❌ API Bağlantı Hatası: {e}")
    exit(1)

def telegrama_yaz(mesaj):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def veri_analiz_et(sembol):
    try:
        ticker = yf.Ticker(sembol)
        df = ticker.history(period="6mo", interval="1d")
        if df.empty: return None

        df['RSI'] = ta.rsi(df['Close'], length=14)
        bb = ta.bbands(df['Close'], length=20, std=2)
        df['BB_UP'] = bb['BBU_20_2.0']
        df['BB_LOW'] = bb['BBL_20_2.0']
        
        son = df.iloc[-1]
        sinyal = "NÖTR ⚪"
        if son['Close'] > son['BB_UP']: sinyal = "ALIM (PATLAMA) 🔥"
        elif son['Close'] < son['BB_LOW']: sinyal = "SATIŞ (DÜŞÜŞ) ❄️"
        elif son['RSI'] < 30: sinyal = "DİP (TOPLA) 🟢"
        elif son['RSI'] > 75: sinyal = "ZİRVE (SAT) 🔴"
        
        return {
            "sembol": sembol,
            "fiyat": round(son['Close'], 2),
            "sinyal": sinyal
        }
    except:
        return None

def raporla():
    if OZEL_ISTEK and len(OZEL_ISTEK) > 1:
        mesaj = f"🔍 **ÖZEL ANALİZ: {OZEL_ISTEK}**\nAnaliz ediliyor..."
        telegrama_yaz(mesaj)
        return

    tarih = datetime.now().strftime('%H:%M')
    mesaj = f"📅 **SAATLİK RAPOR ({tarih})**\n────────────────\n"
    
    for kategori, semboller in SABIT_LISTE.items():
        mesaj += f"\n*{kategori}*\n"
        for sembol in semboller:
            veri = veri_analiz_et(sembol)
            if veri:
                ikon = "🚀" if "🔥" in veri['sinyal'] or "🟢" in veri['sinyal'] else "▪️"
                mesaj += f"{ikon} `{sembol}`: {veri['fiyat']} | {veri['sinyal']}\n"
    
    # Gemini yorumunu buraya ekleyebilirsin, şimdilik temel sistem çalışsın diye kapalı.
    telegrama_yaz(mesaj)
    print("✅ Rapor başarıyla gönderildi.")

if __name__ == "__main__":
    raporla()
