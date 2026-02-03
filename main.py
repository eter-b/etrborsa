import os
import requests
import yfinance as yf
import pandas_ta as ta
import google.generativeai as genai
from datetime import datetime
import pytz

# --- ŞİFRELER ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
OZEL_ISTEK = os.environ.get("OZEL_ISTEK", "")

if not GOOGLE_API_KEY:
    print("❌ API Key Eksik!")
    exit(1)

# --- AYARLAR ---
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# DOĞRU SEMBOLLER (BIST İÇİN .IS KULLANILIR)
SABIT_LISTE = {
    "🛡️ DEFANSİF": ["GC=F", "SI=F", "KCHOL.IS", "SAHOL.IS"], 
    "📈 BÜYÜME": ["THYAO.IS", "ASELS.IS", "TUPRS.IS", "GMSTR.IS"], 
    "🚀 RİSKLİ": ["BTC-USD", "ETH-USD", "SOL-USD"] 
}

def tr_saati():
    tz = pytz.timezone('Europe/Istanbul')
    return datetime.now(tz).strftime('%d.%m.%Y %H:%M')

def telegrama_yaz(mesaj):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mesaj, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def veri_analiz_et(sembol):
    try:
        # Yahoo Finance Engelini Aşmak İçin Tarayıcı Taklidi
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        
        # Veriyi Çek (2 Yıllık - Uzun vade analizi için)
        ticker = yf.Ticker(sembol, session=session)
        df = ticker.history(period="2y", interval="1d")
        
        if df.empty:
            print(f"⚠️ {sembol} verisi boş geldi. Sembolü kontrol et.")
            return None

        # --- ÇOKLU ZAMAN DİLİMİ ANALİZİ ---
        son_fiyat = df['Close'].iloc[-1]
        
        # 1. HAFTALIK DEĞİŞİM (5 işlem günü)
        haftalik_degisim = 0
        if len(df) > 5:
            haftalik_degisim = ((son_fiyat - df['Close'].iloc[-6]) / df['Close'].iloc[-6]) * 100
            
        # 2. AYLIK DEĞİŞİM (22 işlem günü)
        aylik_degisim = 0
        if len(df) > 22:
            aylik_degisim = ((son_fiyat - df['Close'].iloc[-23]) / df['Close'].iloc[-23]) * 100
            
        # 3. YILLIK TREND (200 Günlük Ortalama)
        sma200 = ta.sma(df['Close'], length=200).iloc[-1]
        uzun_vade_trend = "BOĞA (Yükseliş)" if son_fiyat > sma200 else "AYI (Düşüş)"

        # İndikatörler
        rsi = ta.rsi(df['Close'], length=14).iloc[-1]
        bb = ta.bbands(df['Close'], length=20, std=2)
        
        # Sinyal
        sinyal = "NÖTR ⚪"
        bb_up = bb['BBU_20_2.0'].iloc[-1]
        bb_low = bb['BBL_20_2.0'].iloc[-1]
        
        if son_fiyat > bb_up: sinyal = "GÜÇLÜ AL (PATLAMA) 🔥"
        elif son_fiyat < bb_low: sinyal = "GÜÇLÜ SAT (DİP KIRILIMI) ❄️"
        elif rsi < 30: sinyal = "DİP FIRSATI 🟢"
        elif rsi > 75: sinyal = "ZİRVE RİSKİ 🔴"

        return {
            "sembol": sembol,
            "fiyat": round(son_fiyat, 2),
            "sinyal": sinyal,
            "rsi": round(rsi, 1),
            "haftalik": round(haftalik_degisim, 1),
            "aylik": round(aylik_degisim, 1),
            "trend": uzun_vade_trend,
            "sma200": round(sma200, 2)
        }
    except Exception as e:
        print(f"Hata ({sembol}): {e}")
        return None

def raporla():
    # --- ÖZEL İSTEK (KUMANDA İLE) ---
    if OZEL_ISTEK and len(OZEL_ISTEK) > 1:
        sembol = OZEL_ISTEK.upper()
        # Eğer kullanıcı uzantıyı yazmadıysa otomatik ekle
        if "." not in sembol and "=" not in sembol and "-" not in sembol:
            sembol += ".IS"
            
        telegrama_yaz(f"🔍 **{sembol}** için Profesyonel Analiz Hazırlanıyor...")
        veri = veri_analiz_et(sembol)
        
        if veri:
            prompt = f"""
            Sen kıdemli bir borsa stratejistisin. Şu verileri yorumla:
            Varlık: {veri['sembol']}
            Fiyat: {veri['fiyat']}
            Haftalık Değişim: %{veri['haftalik']}
            Aylık Değişim: %{veri['aylik']}
            Uzun Vade Trend (SMA200): {veri['trend']} (Ortalama: {veri['sma200']})
            RSI: {veri['rsi']}
            Sinyal: {veri['sinyal']}
            
            GÖREV:
            1. Bu varlığın kısa, orta ve uzun vadeli fotoğrafını çek.
            2. Giriş seviyesi bir yatırımcıya "Al", "Sat" veya "Bekle" tavsiyesini gerekçesiyle ver.
            3. Üslubun profesyonel ama anlaşılır olsun.
            """
            ai_cevap = model.generate_content(prompt).text
            
            mesaj = f"📊 **{veri['sembol']} DETAY RAPORU**\n"
            mesaj += f"💰 Fiyat: {veri['fiyat']}\n"
            mesaj += f"📅 Haftalık: %{veri['haftalik']} | Aylık: %{veri['aylik']}\n"
            mesaj += f"🌊 Ana Trend: {veri['trend']}\n"
            mesaj += f"🚦 Sinyal: {veri['sinyal']}\n"
            mesaj += "────────────────\n"
            mesaj += f"💡 **UZMAN GÖRÜŞÜ:**\n_{ai_cevap}_"
            telegrama_yaz(mesaj)
        else:
            telegrama_yaz(f"⚠️ `{sembol}` verisi çekilemedi. Kodun doğru olduğundan emin misin? (Örn: THYAO.IS)")
        return

    # --- GENEL SAATLİK RAPOR ---
    print("Genel rapor hazırlanıyor...")
    mesaj = f"🇹🇷 **PİYASA PANORAMASI** ({tr_saati()})\n"
    ham_veri = ""
    
    veri_var = False
    for kategori, semboller in SABIT_LISTE.items():
        mesaj += f"\n*{kategori}*\n"
        ham_veri += f"\n--- {kategori} ---\n"
        for sembol in semboller:
            veri = veri_analiz_et(sembol)
            if veri:
                veri_var = True
                ikon = "▪️"
                if "🔥" in veri['sinyal'] or "🟢" in veri['sinyal']: ikon = "🚀"
                elif "❄️" in veri['sinyal'] or "🔴" in veri['sinyal']: ikon = "⚠️"
                
                # Telegram'a Sade Bilgi
                mesaj += f"{ikon} `{sembol}`: {veri['fiyat']} | {veri['sinyal']}\n"
                
                # Gemini'ye Detaylı Bilgi
                ham_veri += f"{sembol}: Fiyat={veri['fiyat']}, Haftalık=%{veri['haftalik']}, Aylık=%{veri['aylik']}, Trend={veri['trend']}, Sinyal={veri['sinyal']}\n"
            else:
                mesaj += f"❌ `{sembol}`: Veri Yok\n"

    if not veri_var:
        telegrama_yaz("⚠️ Piyasa verilerine ulaşılamıyor. Yahoo Finance sunucularında bakım olabilir.")
        return

    # Gemini Yorumu
    prompt = f"""
    Sen bir portföy yöneticisisin. Aşağıdaki tabloya bak ve özet geç:
    {ham_veri}
    
    GÖREV:
    1. Portföyün genel sağlığı nasıl? (Yükselişte mi, düşüşte mi?)
    2. En dikkat çeken (En çok kazandıran veya kaybettiren) varlık hangisi?
    3. Defansif, Büyüme ve Riskli sepetler için tek cümlelik eylem planı ver.
    """
    try:
        ai_yorum = model.generate_content(prompt).text
        mesaj += "\n────────────────\n"
        mesaj += ai_yorum
    except: pass

    telegrama_yaz(mesaj)

if __name__ == "__main__":
    raporla()
