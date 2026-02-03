import os
import requests
import yfinance as yf
import pandas_ta as ta
import google.generativeai as genai
from datetime import datetime

# --- GITHUB'DAN GELECEK ŞİFRELER ---
# GitHub Actions bu bilgileri "Secrets" kısmından alacak
GOOGLE_API_KEY = os.environ["AIzaSyCPsDQrDvbkjHD0-v97n9d1Nqkcd5qvdCY"]
TELEGRAM_BOT_TOKEN = os.environ["8587911896:AAErzo-BWPdKzi4a1liCNUmLLg2_qBu9Afg"]
TELEGRAM_CHAT_ID = os.environ["1952593958"]

# --- AYARLAR ---
TAKIP_LISTESI = {
    "🛡️ DEFANSİF": ["GC=F", "SI=F", "KCHOL.IS"], 
    "📈 BÜYÜME": ["THYAO.IS", "ASELS.IS", "NVDA"], 
    "🚀 RİSKLİ": ["BTC-USD", "ETH-USD"] 
}

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

def telegrama_yaz(mesaj):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def veri_analiz_et(sembol):
    try:
        ticker = yf.Ticker(sembol)
        df = ticker.history(period="6mo", interval="1d")
        if df.empty: return None

        # --- PROFESYONEL İNDİKATÖRLER ---
        # 1. RSI (Güç)
        df['RSI'] = ta.rsi(df['Close'], length=14)
        
        # 2. Bollinger Bantları (Patlama Sinyali)
        bb = ta.bbands(df['Close'], length=20, std=2)
        df['BB_UP'] = bb['BBU_20_2.0']
        df['BB_LOW'] = bb['BBL_20_2.0']
        
        # 3. MACD (Trend Dönüşü)
        macd = ta.macd(df['Close'])
        df['MACD'] = macd['MACD_12_26_9']
        df['MACD_SIGNAL'] = macd['MACDs_12_26_9']

        son = df.iloc[-1]
        
        # --- SİNYAL MANTIĞI ---
        sinyal = "NÖTR ⚪"
        
        # Bollinger Patlaması (Fiyat üst bandı deldiyse yükseliş sertleşebilir)
        if son['Close'] > son['BB_UP']: sinyal = "GÜÇLÜ ALIM (PATLAMA) 🔥"
        elif son['Close'] < son['BB_LOW']: sinyal = "GÜÇLÜ SATIŞ (ÇÖKÜŞ) ❄️"
        
        # RSI Kontrolü
        elif son['RSI'] < 30: sinyal = "DİP FİYAT (TOPLA) 🟢"
        elif son['RSI'] > 75: sinyal = "TEPE FİYAT (SAT) 🔴"
        
        # MACD Kesişimi (Al/Sat Teyidi)
        macd_yorum = "Pozitif" if son['MACD'] > son['MACD_SIGNAL'] else "Negatif"

        # --- HABER ANALİZİ (YENİ!) ---
        haberler = ticker.news
        haber_basliklari = ""
        if haberler:
            for n in haberler[:2]: # Son 2 haberi al
                haber_basliklari += f"- {n['title']}\n"
        else:
            haber_basliklari = "Önemli haber akışı yok."

        return {
            "sembol": sembol,
            "fiyat": round(son['Close'], 2),
            "sinyal": sinyal,
            "rsi": round(son['RSI'], 1),
            "macd": macd_yorum,
            "haberler": haber_basliklari
        }
    except Exception as e:
        print(f"Hata ({sembol}): {e}")
        return None

def raporla():
    tarih = datetime.now().strftime('%d.%m %H:%M')
    print("Analiz Başlıyor...")
    
    ham_veri = ""
    mesaj = f"📊 **ORACLE PİYASA RAPORU** ({tarih})\n──────────────────\n"

    for kategori, semboller in TAKIP_LISTESI.items():
        mesaj += f"\n*{kategori}*\n"
        for sembol in semboller:
            veri = veri_analiz_et(sembol)
            if veri:
                # Telegram Görünümü
                ikon = "▪️"
                if "🔥" in veri['sinyal'] or "🟢" in veri['sinyal']: ikon = "🚀"
                elif "❄️" in veri['sinyal'] or "🔴" in veri['sinyal']: ikon = "⚠️"
                
                mesaj += f"{ikon} `{sembol}`: {veri['fiyat']} | {veri['sinyal']}\n"
                
                # Gemini için detay veri
                ham_veri += f"VARLIK: {sembol} | FİYAT: {veri['fiyat']} | SİNYAL: {veri['sinyal']} | MACD: {veri['macd']} | HABERLER: {veri['haberler']}\n"

    # --- GEMINI YORUMU ---
    prompt = f"""
    Sen dünyanın en iyi borsa "Oracle"ısın (Kahini). Aşağıdaki teknik verilere ve HABERLERE bakarak strateji kur.
    
    VERİLER:
    {ham_veri}
    
    GÖREV:
    1. Sadece "ALIM" veya "SATIM" fırsatı veren en belirgin 1 varlığı seç.
    2. Nedenini (Teknik + Haber) tek cümleyle açıkla.
    3. Diğerleri için genel bir piyasa uyarısı yap.
    
    Kısa, net ve profesyonel ol.
    """
    
    try:
        yorum = model.generate_content(prompt).text
        mesaj += f"\n💡 **ORACLE GÖRÜŞÜ:**\n_{yorum}_"
    except:
        mesaj += "\n💡 Yorum oluşturulamadı."

    telegrama_yaz(mesaj)

if __name__ == "__main__":
    raporla()
