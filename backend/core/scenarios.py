"""
Sprint 2 — Senaryo Karşılaştırma Motoru.

"İstifa edersem ne kaybederim?", "İkale yaparsam ne talep etmeliyim?",
"3 ay daha çalışırsam ne değişir?" gibi sorular tek bir ayrılış şekli değil,
birden çok alternatifin yan yana hesaplanmasını gerektirir.

Tasarım: Bu motor da tamamen deterministiktir — her senaryo için
core.calculations.hepsini_hesapla() bağımsız olarak çağrılır. LLM burada da
sayı üretmez; yalnızca Planner hangi senaryoların karşılaştırılacağına karar
verir, Insight ise sonucu yorumlar.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date

from core.calculations import CalismaBilgisi, AyrilisSekli, HesapSonucu, hepsini_hesapla, tek_seferlik_toplam, AYRILIS_ETIKETLERI


@dataclass
class SenaryoSonucu:
    ayrilis: str
    etiket: str
    cikis: str
    sonuclar: dict           # {"kidem": HesapSonucu, "ihbar": ..., "issizlik": ...}
    tek_seferlik_toplam: float
    aylik_issizlik: float

    def to_dict(self) -> dict:
        return {
            "ayrilis": self.ayrilis,
            "etiket": self.etiket,
            "cikis": self.cikis,
            "sonuclar": {k: v.to_dict() for k, v in self.sonuclar.items()},
            "tek_seferlik_toplam": self.tek_seferlik_toplam,
            "aylik_issizlik": self.aylik_issizlik,
        }


def senaryo_hesapla(bilgi: CalismaBilgisi, ayrilis: AyrilisSekli, cikis_override: date | None = None) -> SenaryoSonucu:
    b = bilgi.kopya(ayrilis=ayrilis, cikis=cikis_override or bilgi.cikis)
    sonuclar = hepsini_hesapla(b)
    return SenaryoSonucu(
        ayrilis=ayrilis.value,
        etiket=AYRILIS_ETIKETLERI[ayrilis],
        cikis=b.cikis.isoformat(),
        sonuclar=sonuclar,
        tek_seferlik_toplam=tek_seferlik_toplam(sonuclar),
        aylik_issizlik=sonuclar["issizlik"].net if sonuclar["issizlik"].hak_var else 0.0,
    )


def senaryo_karsilastir(
    bilgi: CalismaBilgisi,
    ayrilislar: list[AyrilisSekli],
    ek_cikis_senaryosu: date | None = None,
) -> list[SenaryoSonucu]:
    """
    ayrilislar: karşılaştırılacak ayrılış şekilleri (örn. [ISVEREN_FESHI, ISTIFA, IKALE])
    ek_cikis_senaryosu: verilirse, mevcut ayrılış şekliyle ama farklı bir çıkış
        tarihiyle ek bir senaryo daha hesaplanır ("3 ay daha çalışırsam" sorusu).
    """
    sonuclar = [senaryo_hesapla(bilgi, a) for a in ayrilislar]
    if ek_cikis_senaryosu:
        sonuclar.append(senaryo_hesapla(bilgi, bilgi.ayrilis, cikis_override=ek_cikis_senaryosu))
    return sonuclar
