"""
Financial News Aggregator and Domain-Specific Sentiment Engine
Extracts news via Google News RSS & Yahoo Finance and computes sentiment scores.
Includes optional Gemini AI synthesis when API key is present.
"""
import urllib.parse
import re
from datetime import datetime
import feedparser
import requests
from bs4 import BeautifulSoup
import yfinance as yf
from backend.config import GEMINI_API_KEY

# Specialized Financial Sentiment Lexicons (Loughran-McDonald inspired)
BULLISH_TERMS = {
    "surge": 2.5, "surges": 2.5, "surged": 2.5, "surging": 2.5,
    "rally": 2.0, "rallies": 2.0, "rallied": 2.0, "rallying": 2.0,
    "soar": 2.5, "soars": 2.5, "soared": 2.5, "soaring": 2.5,
    "jump": 1.8, "jumps": 1.8, "jumped": 1.8,
    "skyrocket": 3.0, "skyrockets": 3.0, "skyrocketed": 3.0,
    "breakout": 2.2, "breakouts": 2.2, "breaking out": 2.2,
    "bullish": 2.0, "bull": 1.5, "bulls": 1.5,
    "beat": 2.0, "beats": 2.0, "beaten expectations": 2.5,
    "record high": 2.5, "all-time high": 2.8, "52-week high": 2.2,
    "outperform": 2.2, "outperformed": 2.2, "outperforming": 2.2,
    "upgrade": 2.2, "upgrades": 2.2, "upgraded": 2.2,
    "profit": 1.5, "profits": 1.5, "profitable": 1.5,
    "revenue jump": 2.2, "revenue growth": 2.0, "growth": 1.5,
    "dividend": 1.2, "bonus issue": 1.8, "buyback": 2.0,
    "gain": 1.2, "gains": 1.2, "gained": 1.2, "gaining": 1.2,
    "order win": 2.2, "contract": 1.4, "deal": 1.3, "expansion": 1.5,
    "strong": 1.5, "blockbuster": 2.5, "robust": 1.8, "solid": 1.4,
    "turnaround": 2.0, "optimistic": 1.5, "positive": 1.2,
    "approval": 1.8, "approved": 1.8, "partnership": 1.5,
    "subscribed": 1.8, "oversubscribed": 2.5, "listing gain": 2.0
}

BEARISH_TERMS = {
    "plunge": -2.5, "plunges": -2.5, "plunged": -2.5, "plunging": -2.5,
    "slump": -2.2, "slumps": -2.2, "slumped": -2.2, "slumping": -2.2,
    "crash": -3.0, "crashes": -3.0, "crashed": -3.0, "crashing": -3.0,
    "tumble": -2.2, "tumbles": -2.2, "tumbled": -2.2, "tumbling": -2.2,
    "drop": -1.5, "drops": -1.5, "dropped": -1.5, "dropping": -1.5,
    "fall": -1.5, "falls": -1.5, "fell": -1.5, "falling": -1.5,
    "loss": -2.0, "losses": -2.0, "losing": -1.5,
    "bearish": -2.0, "bear": -1.5, "bears": -1.5,
    "miss": -2.0, "misses": -2.0, "missed": -2.0,
    "downgrade": -2.2, "downgrades": -2.2, "downgraded": -2.2,
    "probe": -2.5, "probes": -2.5, "investigation": -2.2, "fraud": -3.5,
    "penalty": -2.0, "fine": -1.8, "scam": -3.5, "raid": -2.8,
    "default": -3.0, "defaults": -3.0, "debt crisis": -3.0,
    "lawsuit": -2.0, "sued": -2.0, "litigation": -1.8,
    "layoffs": -1.8, "firing": -1.8, "cuts": -1.4,
    "slashed": -2.0, "weak": -1.6, "weakness": -1.6,
    "inflation": -1.2, "recession": -2.5, "slowdown": -1.8,
    "52-week low": -2.2, "record low": -2.5, "near low": -1.5,
    "warning": -1.8, "caution": -1.2, "risk": -1.0, "risks": -1.0,
    "halt": -2.0, "suspended": -2.5, "ban": -2.5, "banned": -2.5
}

INTENSIFIERS = {
    "massive": 1.6, "blockbuster": 1.7, "huge": 1.5, "sharp": 1.4,
    "steep": 1.4, "solid": 1.3, "slight": 0.5, "slightly": 0.5, "modest": 0.6
}

NEGATIONS = {"not", "no", "never", "failed", "fails", "failing", "neither", "hardly", "despite"}


class NewsSentimentAnalyzer:
    """Aggregates real-time financial news and analyzes market sentiment."""

    def __init__(self, gemini_api_key: str = None):
        self.api_key = gemini_api_key or GEMINI_API_KEY
        self.client = None
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception:
                pass

    def fetch_news(self, symbol: str, company_name: str = "", limit: int = 15) -> list:
        """Fetch news from Google News RSS and Yahoo Finance."""
        articles = []
        clean_name = company_name or symbol.replace(".NS", "").replace(".BO", "")
        search_query = f"{clean_name} stock OR share"
        
        # 1. Fetch via Google News RSS
        is_indian = ".NS" in symbol or ".BO" in symbol or "NIFTY" in symbol
        gl = "IN" if is_indian else "US"
        hl = "en-IN" if is_indian else "en-US"
        ceid = "IN:en" if is_indian else "US:en"

        encoded_q = urllib.parse.quote(search_query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl={hl}&gl={gl}&ceid={ceid}"
        
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries[:limit]:
                # Extract clean title and publisher
                title_full = entry.title
                source = "News"
                if " - " in title_full:
                    parts = title_full.rsplit(" - ", 1)
                    title = parts[0].strip()
                    source = parts[1].strip()
                else:
                    title = title_full.strip()

                published_at = entry.get("published", "")
                link = entry.get("link", "")

                articles.append({
                    "title": title,
                    "source": source,
                    "published": published_at,
                    "link": link,
                    "origin": "Google News"
                })
        except Exception as e:
            print(f"[News] Google RSS error: {e}")

        # 2. Also check yfinance news if list is short
        if len(articles) < 5:
            try:
                yf_ticker = yf.Ticker(symbol)
                yf_news = yf_ticker.news or []
                for item in yf_news[:5]:
                    title = item.get("title", "")
                    if not title and "content" in item:
                        title = item["content"].get("title", "")
                    if title and not any(a["title"] == title for a in articles):
                        articles.append({
                            "title": title,
                            "source": item.get("publisher", "Yahoo Finance"),
                            "published": str(datetime.fromtimestamp(item.get("providerPublishTime", 0))),
                            "link": item.get("link", ""),
                            "origin": "Yahoo Finance"
                        })
            except Exception as e:
                print(f"[News] Yahoo news error: {e}")

        return articles[:limit]

    def score_headline(self, headline: str) -> dict:
        """Evaluate sentiment score for a single headline using financial lexicons."""
        text = headline.lower()
        # Clean punctuation
        words = re.findall(r"\b[a-zA-Z\-]+\b", text)

        score = 0.0
        negated = False
        multiplier = 1.0
        matched_terms = []

        for i, word in enumerate(words):
            if word in NEGATIONS:
                negated = True
                continue
            if word in INTENSIFIERS:
                multiplier = INTENSIFIERS[word]
                continue

            # Check multi-word phrases first
            two_words = f"{words[i-1]} {word}" if i > 0 else ""
            if two_words in BULLISH_TERMS:
                val = BULLISH_TERMS[two_words] * multiplier * (-1.0 if negated else 1.0)
                score += val
                matched_terms.append((two_words, val))
                negated = False
                multiplier = 1.0
                continue
            elif two_words in BEARISH_TERMS:
                val = BEARISH_TERMS[two_words] * multiplier * (-1.0 if negated else 1.0)
                score += val
                matched_terms.append((two_words, val))
                negated = False
                multiplier = 1.0
                continue

            if word in BULLISH_TERMS:
                val = BULLISH_TERMS[word] * multiplier * (-1.0 if negated else 1.0)
                score += val
                matched_terms.append((word, val))
                negated = False
                multiplier = 1.0
            elif word in BEARISH_TERMS:
                val = BEARISH_TERMS[word] * multiplier * (-1.0 if negated else 1.0)
                score += val
                matched_terms.append((word, val))
                negated = False
                multiplier = 1.0

        # Normalize score into range [-1.0, 1.0]
        norm_score = max(min(score / 3.0, 1.0), -1.0)
        
        if norm_score >= 0.15:
            sentiment_tag = "POSITIVE"
        elif norm_score <= -0.15:
            sentiment_tag = "NEGATIVE"
        else:
            sentiment_tag = "NEUTRAL"

        return {
            "score": round(norm_score, 3),
            "sentiment": sentiment_tag,
            "matched_terms": matched_terms
        }

    def analyze(self, symbol: str, company_name: str = "") -> dict:
        """Perform comprehensive news sentiment analysis on the stock."""
        news_items = self.fetch_news(symbol, company_name, limit=12)
        if not news_items:
            return {
                "symbol": symbol,
                "net_sentiment": 0.0,
                "sentiment_label": "NEUTRAL",
                "confidence": 50,
                "breakdown": {"positive": 0, "neutral": 0, "negative": 0},
                "total_articles": 0,
                "articles": [],
                "ai_summary": "No recent breaking news detected for this symbol."
            }

        scored_articles = []
        total_score = 0.0
        pos_count = 0
        neg_count = 0
        neu_count = 0

        for item in news_items:
            res = self.score_headline(item["title"])
            item["sentiment_score"] = res["score"]
            item["sentiment"] = res["sentiment"]
            total_score += res["score"]

            if res["sentiment"] == "POSITIVE":
                pos_count += 1
            elif res["sentiment"] == "NEGATIVE":
                neg_count += 1
            else:
                neu_count += 1

            scored_articles.append(item)

        total = len(scored_articles)
        avg_score = total_score / total if total > 0 else 0.0
        # Scale between -1.0 and 1.0
        net_score = round(max(min(avg_score, 1.0), -1.0), 3)

        if net_score >= 0.35:
            label = "STRONGLY BULLISH"
        elif net_score >= 0.10:
            label = "BULLISH"
        elif net_score <= -0.35:
            label = "STRONGLY BEARISH"
        elif net_score <= -0.10:
            label = "BEARISH"
        else:
            label = "NEUTRAL"

        confidence = min(int(abs(net_score) * 60 + (pos_count + neg_count) * 4), 95)

        # AI Summary synthesis
        ai_summary = self._generate_ai_summary(clean_name=company_name or symbol, 
                                              articles=scored_articles, 
                                              net_score=net_score, 
                                              label=label)

        return {
            "symbol": symbol,
            "company_name": company_name or symbol,
            "net_sentiment": net_score,
            "sentiment_label": label,
            "confidence": confidence,
            "breakdown": {
                "positive": pos_count,
                "neutral": neu_count,
                "negative": neg_count
            },
            "total_articles": total,
            "articles": scored_articles,
            "ai_summary": ai_summary
        }

    def _generate_ai_summary(self, clean_name: str, articles: list, net_score: float, label: str) -> str:
        """Produce an AI executive summary of market sentiment."""
        # Check if Gemini API client is available
        if self.client:
            try:
                headlines_sample = "\n".join([f"- {a['title']} ({a['sentiment']})" for a in articles[:6]])
                prompt = (
                    f"You are a Wall Street & Dalal Street senior quantitative analyst. "
                    f"Analyze the following recent news headlines for '{clean_name}':\n{headlines_sample}\n"
                    f"Our quantified sentiment score is {net_score} ({label}). "
                    f"Provide a concise, 2-3 sentence executive market summary explaining the primary drivers, "
                    f"key catalysts, and potential risks for short-term traders."
                )
                response = self.client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                print(f"[News] Gemini API error, falling back to rule summary: {e}")

        # Rule-based institutional synthesis
        positives = [a['title'] for a in articles if a['sentiment'] == 'POSITIVE']
        negatives = [a['title'] for a in articles if a['sentiment'] == 'NEGATIVE']

        summary_parts = [f"Market sentiment for {clean_name} is currently **{label}** (score: {net_score:+.2f})."]
        if positives:
            summary_parts.append(f"Bullish catalysts include positive coverage on '{positives[0][:80]}...'.")
        if negatives:
            summary_parts.append(f"Key headwinds or risks highlighted: '{negatives[0][:80]}...'.")
        if not positives and not negatives:
            summary_parts.append("News flow is balanced with no major disruptive catalysts reported in the last 24 hours.")

        return " ".join(summary_parts)
