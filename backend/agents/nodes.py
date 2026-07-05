"""
LangGraph düğümleri: Planner → Calculator → Critic → Insight

İş bölümü ilkesi:
- Planner (LLM): kullanıcının serbest metin sorusunu yorumlar → hangi
  kalemler hesaplanacak, kullanıcı hangi senaryoyu soruyor.
- Calculator (deterministik): core/calculations çağrılır. LLM para hesabı YAPMAZ.
- Critic (deterministik + Reflexion iskeleti): core/validators ile bağımsız
  denetim; ihlal varsa düzeltme talimatıyla Calculator'a geri döner.
- Insight (LLM): doğrulanmış sonucu, kullanıcının sorusuna hitap eden
  sade Türkçe bir açıklamaya çevirir.

GEMINI_API_KEY yoksa sistem DEMO modunda çalışır: Planner tüm kalemleri
seçer, Insight şablon metin üretir. Böylece hat, API anahtarı olmadan da
uçtan uca test edilebilir (Sprint 1 gereksinimi).
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict

from core.calculations import CalismaBilgisi, hepsini_hesapla
from core.validators import check

GEMINI_MODEL = "gemini-2.0-flash"
MAX_RETRY = 3


def _client():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    from google import genai
    return genai.Client(api_key=key)


def _llm(prompt: str) -> str | None:
    c = _client()
    if c is None:
        return None
    resp = c.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    return resp.text


# ---------------------------------------------------------------- Planner
def planner_node(state: dict) -> dict:
    soru = state.get("soru", "").strip()
    plan = {"kalemler": ["kidem", "ihbar", "issizlik"], "odak": None}

    if soru:
        yanit = _llm(
            "Kullanıcı, Türkiye'de işten ayrılma durumunda alacağı ödemeleri soruyor.\n"
            f"Soru: \"{soru}\"\n\n"
            "Hangi kalemler ilgili? Seçenekler: kidem, ihbar, issizlik.\n"
            "SADECE şu JSON'u döndür, başka hiçbir şey yazma:\n"
            '{"kalemler": ["..."], "odak": "sorunun tek cümlelik özü"}'
        )
        if yanit:
            try:
                temiz = yanit.replace("```json", "").replace("```", "").strip()
                parsed = json.loads(temiz)
                if parsed.get("kalemler"):
                    plan["kalemler"] = [k for k in parsed["kalemler"] if k in ("kidem", "ihbar", "issizlik")] or plan["kalemler"]
                plan["odak"] = parsed.get("odak")
            except (json.JSONDecodeError, AttributeError):
                pass  # plan varsayılanda kalır — Critic felsefesi: bozuk LLM çıktısı hattı durdurmaz

    return {**state, "plan": plan}


# ------------------------------------------------------------- Calculator
def calculator_node(state: dict) -> dict:
    bilgi: CalismaBilgisi = state["bilgi"]
    sonuclar = hepsini_hesapla(bilgi)
    secili = {k: v for k, v in sonuclar.items() if k in state["plan"]["kalemler"]}
    return {**state, "sonuclar": secili, "retry": state.get("retry", 0)}


# ------------------------------------------------------------------ Critic
def critic_node(state: dict) -> dict:
    ihlaller = check(state["bilgi"], state["sonuclar"])
    return {**state, "ihlaller": ihlaller}


def critic_router(state: dict) -> str:
    """Reflexion kararı: ihlal varsa ve deneme hakkı bitmediyse hesaba geri dön."""
    if state["ihlaller"] and state.get("retry", 0) < MAX_RETRY:
        return "retry"
    return "ok"


def retry_node(state: dict) -> dict:
    # Sprint 1: deterministik motorda ihlal beklemiyoruz; bu düğüm Reflexion
    # iskeletidir. Sprint 2'de LLM-üretimli hesap/kod buradan düzeltme
    # talimatı alarak yeniden üretilecek.
    return {**state, "retry": state.get("retry", 0) + 1}


# ----------------------------------------------------------------- Insight
def _demo_aciklama(state: dict) -> str:
    parcalar = ["## Sonuçlarınız\n"]
    isimler = {"kidem": "Kıdem tazminatı", "ihbar": "İhbar tazminatı", "issizlik": "İşsizlik ödeneği"}
    for k, s in state["sonuclar"].items():
        if s.hak_var:
            parcalar.append(f"**{isimler[k]}:** net **{s.net:,.2f} TL**")
        else:
            parcalar.append(f"**{isimler[k]}:** hak doğmuyor — {s.notlar[0] if s.notlar else ''}")
    if state["ihlaller"]:
        parcalar.append(f"\n⚠️ Doğrulama uyarıları: {state['ihlaller']}")
    else:
        parcalar.append("\n✅ Tüm tutarlar bağımsız doğrulama kurallarından geçti.")
    return "\n\n".join(parcalar)


def insight_node(state: dict) -> dict:
    veri = {k: v.to_dict() for k, v in state["sonuclar"].items()}
    soru = state.get("soru", "")

    yanit = _llm(
        "Sen Türkiye iş hukuku ödemeleri konusunda yardımcı bir asistansın. "
        "Aşağıdaki DOĞRULANMIŞ hesap sonuçlarını kullanıcıya sade Türkçeyle açıkla. "
        "TUTARLARI ASLA DEĞİŞTİRME veya yeniden hesaplama — sadece verilen rakamları kullan. "
        "Kullanıcının sorusuna doğrudan cevap vererek başla, sonra kalemleri kısaca açıkla. "
        "Sonda tek cümlelik 'bu bir ön hesaplamadır, kesin tutar bordro ve SGK kayıtlarına göre değişebilir' notu düş.\n\n"
        f"Kullanıcının sorusu: \"{soru or 'İşten ayrılırsam ne alırım?'}\"\n\n"
        f"Hesap sonuçları (JSON):\n{json.dumps(veri, ensure_ascii=False, indent=2, default=str)}"
    )
    aciklama = yanit if yanit else _demo_aciklama(state)
    return {**state, "aciklama": aciklama, "demo_mode": yanit is None}
