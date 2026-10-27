# ☁️ StockAI Free Cloud Hosting Guide (24/7 Zero Cost)

ఈ గైడ్ ద్వారా మీ StockAI బోట్ బ్యాకెండ్‌ను 100% ఉచితంగా క్లౌడ్‌లో హోస్ట్ చేసుకోవచ్చు. మీ కంప్యూటర్ ఆఫ్‌లో ఉన్నా సరే మీ ఆండ్రాయిడ్ యాప్ 24 గంటలు పని చేస్తుంది!

---

## 🚀 ఆప్షన్ 1: Render.com లో 1-క్లిక్ ఫ్రీ డిప్లాయ్‌మెంట్ (సిఫార్సు చేయబడింది)

Render.com లో క్రెడిట్ కార్డు అవసరం లేకుండా ఉచితంగా Python FastAPI యాప్‌ను హోస్ట్ చేయవచ్చు:

### స్టెప్స్:
1. **[Render.com](https://render.com)** వెబ్‌సైట్‌కి వెళ్లి **Sign Up with Google / GitHub** తో ఫ్రీ అకౌంట్ క్రియేట్ చేసుకోండి.
2. Dashboard లో పైన **New +** బటన్ నొక్కి **"Web Service"** సెలెక్ట్ చేయండి.
3. మీ ప్రాజెక్ట్ గిట్‌హబ్ రిపోజిటరీని లింక్ చేయండి (లేదా "Public Git repository" లింక్ ఇవ్వండి).
4. కింది సెట్టింగ్స్ ఇవ్వండి:
   - **Name**: `stockai-bot`
   - **Region**: Singapore (ఆసియా/ఇండియా కి దగ్గరగా ఉండి వేగంగా ఉంటుంది)
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: `Free` ($0/month)
5. **"Deploy Web Service"** బటన్ నొక్కండి!
6. 2 నిమిషాల్లో Render మీకు ఒక లైవ్ HTTPS URL ఇస్తుంది (ఉదాహరణకు: `https://stockai-bot-xyz.onrender.com`).

---

## 📱 ఆండ్రాయిడ్ యాప్‌లో క్లౌడ్ URL ఎలా కనెక్ట్ చేయాలి?

1. మీ ఫోన్‌లో [`StockAI-bot.apk`](file:///c:/Users/jatot/Downloads/stock%20ai/StockAI-bot.apk) ఓపెన్ చేయండి.
2. కింద ఉన్న **⚙️ Settings** ట్యాబ్ మీద క్లిక్ చేయండి.
3. **"🌐 Bot Backend Connection"** బాక్స్‌లో Render ఇచ్చిన క్లౌడ్ URL (ఉదా: `https://stockai-bot-xyz.onrender.com`) పేస్ట్ చేయండి.
4. **"💾 Save & Connect"** బటన్ నొక్కండి!

🎉 **అంతే! ఇప్పుడు మీ PC పూర్తిగా ఆఫ్ చేసినా సరే, మీ ఫోన్‌లో యాప్ లైవ్ డేటా, AI ట్రేడ్స్ మరియు అలర్ట్స్ 24/7 రన్ అవుతూనే ఉంటాయి!**
