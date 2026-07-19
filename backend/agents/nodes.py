"""
LangGraph düğümleri.

Sprint 1: Planner → Calculator → Critic → Insight (tekli hesap)
Sprint 2 eklentileri:
  - Planner artık senaryo karşılaştırma isteğini tanıyor ("istifa edersem ne
    kaybederim", "ikale yaparsam", "3 ay daha çalışırsam" gibi sorular).
  - Yeni dal: senaryo_calculator → senaryo_critic → insight (grafik + karşılaştırma).
  - Konuşma hafızası: state["gecmis"] önceki soru-cevapları taşır, Insight
    follow-up sorularda bunu bağlam olarak kullanır.

İş bölümü ilkesi hâlâ geçerli: para hesabı LLM'e bırakılmaz. Planner sadece
"hangi senaryolar" sorusuna karar verir; sayıları core.calculations /
core.scenarios üretir.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date

from core.calculations import CalismaBilgisi, AyrilisSekli, hepsini_hesapla
from core.scenarios import senaryo_karsilastir, SenaryoSonucu
from core.validators import check, check_senaryo_tutarliligi
from agents.charts import senaryo_grafigi

GEMINI_MODEL = "gemini-2.0-flash"
MAX_RETRY = 3

AYRILIS_ANAHTAR_KELIME = {
    "istifa": AyrilisSekli.ISTIFA,
    "ikale": AyrilisSekli.IKALE,
    "bozma sözleşmesi": AyrilisSekli.IKALE,
    "işveren": AyrilisSekli.ISVEREN_FESHI,
    "çıkarıl": AyrilisSekli.ISVEREN_FESHI,
    "kovul": AyrilisSekli.ISVEREN_FESHI,
    "emekli": AyrilisSekli.EMEKLILIK,
    "askerlik": AyrilisSekli.ASKERLIK,
}

KARSILASTIRMA_ANAHTAR_KELIME = [
    "karşılaştır", " vs ", "ne kaybederim", "ne fark", "ne değişir",
    "hangisi daha", "kıyasla", "istifa etsem", "ikale yapsam",
]

AY_KALIBI = re.compile(r"(\d+)\s*ay")


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


def _ay_ekle(d: date, ay: int) -> date:
    toplam_ay = d.month - 1 + ay
    yil = d.year + toplam_ay // 12
    ay_no = toplam_ay % 12 + 1
    gun = min(d.day, 28)  # basit ve güvenli: ay sonu taşmalarını engeller
    return date(yil, ay_no, gun)


def _tr_lower(metin: str) -> str:
    """Türkçe İ/I harflerini doğru küçültür (Python'un varsayılan .lower()'ı
    'İ' harfini 'i' + birleşik nokta işaretine çevirir, bu da alt-dizge
    eşleşmelerini bozar — HakKazan'ın veri temizleme sürecinde de karşılaşılan
    klasik bir hatadır)."""
    return metin.replace("İ", "i").replace("I", "ı").lower()


def _heuristik_plan(soru: str, mevcut_ayrilis: AyrilisSekli, cikis: date) -> dict:
    s = _tr_lower(soru)
    senaryolar: list[AyrilisSekli] = []
    for kelime, ayrilis in AYRILIS_ANAHTAR_KELIME.items():
        if kelime in s and ayrilis not in senaryolar:
            senaryolar.append(ayrilis)

    karsilastirma = any(k in s for k in KARSILASTIRMA_ANAHTAR_KELIME) or len(senaryolar) >= 1

    ek_ay = None
    m = AY_KALIBI.search(s)
    if m and ("daha çalış" in s or "sonra" in s or "beklersem" in s):
        ek_ay = int(m.group(1))

    if karsilastirma and not senaryolar and ek_ay is None:
        # Genel karşılaştırma isteği ama hangi senaryo belirtilmemiş: istifa ile kıyasla
        senaryolar = [mevcut_ayrilis, AyrilisSekli.ISTIFA] if mevcut_ayrilis != AyrilisSekli.ISTIFA \
            else [mevcut_ayrilis, AyrilisSekli.ISVEREN_FESHI]
    elif ek_ay is not None and not senaryolar:
        # Salt "X ay daha çalışsam" sorusu: başka senaryo eklemeden aynı ayrılış
        # şeklini iki farklı çıkış tarihiyle kıyasla.
        senaryolar = [mevcut_ayrilis]
    if karsilastirma and mevcut_ayrilis not in senaryolar and ek_ay is None:
        senaryolar.insert(0, mevcut_ayrilis)

    return {
        "kalemler": ["kidem", "ihbar", "issizlik"],
        "odak": soru or None,
        "senaryo_karsilastirma": karsilastirma,
        "senaryolar": [a.value for a in senaryolar],
        "ek_ay": ek_ay,
    }


# ---------------------------------------------------------------- Planner
def planner_node(state: dict) -> dict:
    soru = state.get("soru", "").strip()
    bilgi: CalismaBilgisi = state["bilgi"]
    plan = _heuristik_plan(soru, bilgi.ayrilis, bilgi.cikis)

    if soru:
        yanit = _llm(
            "Kullanıcı, Türkiye'de işten ayrılma durumunda alacağı ödemeleri soruyor. "
            f"Mevcut ayrılış şekli: {bilgi.ayrilis.value}. Soru: \"{soru}\"\n\n"
            "Bu soru birden fazla senaryonun (örn. istifa vs işveren feshi vs ikale, "
            "ya da farklı bir çıkış tarihi) karşılaştırılmasını mı istiyor, yoksa tek "
            "bir hesap mı yeterli? SADECE şu JSON'u döndür, başka hiçbir şey yazma:\n"
            '{"senaryo_karsilastirma": true/false, '
            '"senaryolar": ["isveren_feshi"|"istifa"|"ikale"|"isci_hakli_fesih"|"emeklilik"|"askerlik"], '
            '"ek_ay": null veya sayı (kaç ay daha çalışsa sorusu varsa), '
            '"odak": "sorunun tek cümlelik özü"}'
        )
        if yanit:
            try:
                temiz = yanit.replace("```json", "").replace("```", "").strip()
                parsed = json.loads(temiz)
                if "senaryo_karsilastirma" in parsed:
                    plan["senaryo_karsilastirma"] = bool(parsed["senaryo_karsilastirma"])
                if parsed.get("senaryolar"):
                    gecerli = [a for a in parsed["senaryolar"] if a in AyrilisSekli._value2member_map_]
                    if gecerli:
                        plan["senaryolar"] = gecerli
                if "ek_ay" in parsed and parsed["ek_ay"]:
                    plan["ek_ay"] = int(parsed["ek_ay"])
                plan["odak"] = parsed.get("odak", plan.get("odak"))
            except (json.JSONDecodeError, AttributeError, ValueError, TypeError):
                pass  # LLM çıktısı bozuksa heuristik plan geçerliliğini korur

    return {**state, "plan": plan}


def planner_router(state: dict) -> str:
    return "senaryo" if state["plan"].get("senaryo_karsilastirma") else "tekli"


# ------------------------------------------------------------- Calculator (tekli)
def calculator_node(state: dict) -> dict:
    bilgi: CalismaBilgisi = state["bilgi"]
    sonuclar = hepsini_hesapla(bilgi)
    secili = {k: v for k, v in sonuclar.items() if k in state["plan"]["kalemler"]}
    return {**state, "sonuclar": secili, "retry": state.get("retry", 0)}


def critic_node(state: dict) -> dict:
    ihlaller = check(state["bilgi"], state["sonuclar"])
    return {**state, "ihlaller": ihlaller}


def critic_router(state: dict) -> str:
    if state["ihlaller"] and state.get("retry", 0) < MAX_RETRY:
        return "retry"
    return "ok"


def retry_node(state: dict) -> dict:
    return {**state, "retry": state.get("retry", 0) + 1}


# --------------------------------------------------- Senaryo Calculator (Sprint 2)
def senaryo_calculator_node(state: dict) -> dict:
    bilgi: CalismaBilgisi = state["bilgi"]
    plan = state["plan"]
    ayrilislar = [AyrilisSekli(a) for a in plan["senaryolar"]] or [bilgi.ayrilis]

    ek_cikis = None
    if plan.get("ek_ay"):
        ek_cikis = _ay_ekle(bilgi.cikis, plan["ek_ay"])

    senaryolar = senaryo_karsilastir(bilgi, ayrilislar, ek_cikis_senaryosu=ek_cikis)
    return {**state, "senaryolar": senaryolar, "retry": state.get("retry", 0)}


def senaryo_critic_node(state: dict) -> dict:
    senaryolar: list[SenaryoSonucu] = state["senaryolar"]
    ihlaller: list[str] = []
    for s in senaryolar:
        b_gecici = state["bilgi"].kopya(ayrilis=AyrilisSekli(s.ayrilis), cikis=date.fromisoformat(s.cikis))
        ihlaller += check(b_gecici, s.sonuclar)
    ihlaller += check_senaryo_tutarliligi(senaryolar)
    return {**state, "ihlaller": ihlaller}


def senaryo_critic_router(state: dict) -> str:
    if state["ihlaller"] and state.get("retry", 0) < MAX_RETRY:
        return "retry"
    return "ok"


# ----------------------------------------------------------------- Insight
def _demo_aciklama_tekli(state: dict) -> str:
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


def _demo_aciklama_senaryo(state: dict) -> str:
    parcalar = ["## Senaryo Karşılaştırması\n"]
    for s in state["senaryolar"]:
        parcalar.append(
            f"**{s.etiket}** ({s.cikis}): tek seferlik toplam **{s.tek_seferlik_toplam:,.2f} TL**"
            + (f", aylık işsizlik **{s.aylik_issizlik:,.2f} TL**" if s.aylik_issizlik else "")
        )
    if state["ihlaller"]:
        parcalar.append(f"\n⚠️ Doğrulama uyarıları: {state['ihlaller']}")
    else:
        parcalar.append("\n✅ Senaryolar arası tutarlılık kontrolünden geçti.")
    return "\n\n".join(parcalar)


def insight_node(state: dict) -> dict:
    soru = state.get("soru", "")
    gecmis = state.get("gecmis", [])
    baglam = ""
    if gecmis:
        son = gecmis[-1]
        baglam = (
            f"\n\nÖnceki konuşma bağlamı — kullanıcı daha önce şunu sordu: \"{son.get('soru','')}\" "
            f"ve şu cevabı aldı: \"{son.get('aciklama','')[:400]}\". "
            "Yeni soru bu bağlamın devamı olabilir (takip sorusu)."
        )

    if state.get("senaryolar"):
        veri = [s.to_dict() for s in state["senaryolar"]]
        yanit = _llm(
            "Sen Türkiye iş hukuku ödemeleri konusunda yardımcı bir asistansın. Aşağıda birden "
            "fazla SENARYONUN doğrulanmış hesap sonuçları var. Kullanıcının sorusuna doğrudan "
            "cevap ver, sonra senaryoları kısaca karşılaştır (hangisi ne kadar fark yaratıyor). "
            "TUTARLARI ASLA DEĞİŞTİRME — sadece verilenleri kullan. Sonda 'bu bir ön hesaplamadır' "
            f"notu düş.{baglam}\n\nKullanıcının sorusu: \"{soru}\"\n\n"
            f"Senaryo sonuçları (JSON):\n{json.dumps(veri, ensure_ascii=False, indent=2, default=str)}"
        )
        aciklama = yanit if yanit else _demo_aciklama_senaryo(state)
        grafik = senaryo_grafigi(state["senaryolar"])
        return {**state, "aciklama": aciklama, "grafik": grafik, "demo_mode": yanit is None}

    veri = {k: v.to_dict() for k, v in state["sonuclar"].items()}
    yanit = _llm(
        "Sen Türkiye iş hukuku ödemeleri konusunda yardımcı bir asistansın. Aşağıdaki DOĞRULANMIŞ "
        "hesap sonuçlarını kullanıcıya sade Türkçeyle açıkla. TUTARLARI ASLA DEĞİŞTİRME. Kullanıcının "
        "sorusuna doğrudan cevap vererek başla. Sonda tek cümlelik 'bu bir ön hesaplamadır' notu düş."
        f"{baglam}\n\nKullanıcının sorusu: \"{soru or 'İşten ayrılırsam ne alırım?'}\"\n\n"
        f"Hesap sonuçları (JSON):\n{json.dumps(veri, ensure_ascii=False, indent=2, default=str)}"
    )
    aciklama = yanit if yanit else _demo_aciklama_tekli(state)
    return {**state, "aciklama": aciklama, "grafik": None, "demo_mode": yanit is None}
