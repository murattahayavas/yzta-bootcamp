"""
Yasal parametreler — tek doğruluk kaynağı (single source of truth).

ÖNEMLİ: Bu değerler dönemseldir. Kıdem tavanı her Ocak ve Temmuz'da
(memur maaş katsayısıyla) güncellenir; asgari ücret her Ocak'ta belirlenir.
Yeni dönem açıklandığında SADECE bu dosyaya satır eklenir — hesaplama
kodu değişmez.

Kaynaklar (son güncelleme: Temmuz 2026):
- Kıdem tavanı 01.01.2026–30.06.2026: 64.948,77 TL (Hazine ve Maliye Bakanlığı Genelgesi)
- Kıdem tavanı 01.07.2026–31.12.2026: 73.729,84 TL (Temmuz 2026 memur maaş katsayısı)
- Brüt asgari ücret 2026: 33.030,00 TL/ay (Asgari Ücret Tespit Komisyonu)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Period:
    start: date
    end: date
    value: float


# ---- Kıdem tazminatı tavanı (yıllık, brüt) ----
KIDEM_TAVANI: list[Period] = [
    Period(date(2025, 7, 1), date(2025, 12, 31), 53_919.68),
    Period(date(2026, 1, 1), date(2026, 6, 30), 64_948.77),
    Period(date(2026, 7, 1), date(2026, 12, 31), 73_729.84),
]

# ---- Brüt asgari ücret (aylık) ----
ASGARI_UCRET_BRUT: list[Period] = [
    Period(date(2025, 1, 1), date(2025, 12, 31), 26_005.50),
    Period(date(2026, 1, 1), date(2026, 12, 31), 33_030.00),
]

# ---- Sabit oranlar ----
DAMGA_VERGISI_ORANI = 0.00759  # binde 7,59
ISSIZLIK_ODENEK_ORANI = 0.40   # son 4 ay ort. brüt günlük ücretin %40'ı
ISSIZLIK_TAVAN_ORANI = 0.80    # brüt asgari ücretin %80'i

# İhbar süreleri (kıdem gün aralığı -> hafta)  [İş K. m.17]
IHBAR_HAFTALARI = [
    (0, 180, 2),        # 6 aydan az
    (180, 540, 4),      # 6 ay – 1,5 yıl
    (540, 1080, 6),     # 1,5 – 3 yıl
    (1080, 10**9, 8),   # 3 yıldan fazla
]

# İşsizlik ödeneği süresi (son 3 yıl prim günü -> ödenek günü) [4447 s.K.]
ISSIZLIK_SURELERI = [
    (600, 180),
    (900, 240),
    (1080, 300),
]

# Gelir vergisi dilim oranları (ihbar tazminatı için marjinal oran seçimi)
VERGI_DILIMLERI = [0.15, 0.20, 0.27, 0.35, 0.40]


class RuleNotFoundError(Exception):
    """İlgili tarih için yasal parametre tanımlı değil."""


def _lookup(periods: list[Period], when: date, name: str) -> float:
    for p in periods:
        if p.start <= when <= p.end:
            return p.value
    raise RuleNotFoundError(
        f"{name} için {when.isoformat()} tarihine ait parametre tanımlı değil. "
        f"core/rules.py güncellenmeli."
    )


def kidem_tavani(when: date) -> float:
    return _lookup(KIDEM_TAVANI, when, "Kıdem tazminatı tavanı")


def asgari_ucret_brut(when: date) -> float:
    return _lookup(ASGARI_UCRET_BRUT, when, "Brüt asgari ücret")


def ihbar_haftasi(kidem_gun: int) -> int:
    for lo, hi, hafta in IHBAR_HAFTALARI:
        if lo <= kidem_gun < hi:
            return hafta
    raise ValueError(f"Geçersiz kıdem günü: {kidem_gun}")


def issizlik_gun(prim_gun_son3yil: int) -> int:
    """Son 3 yıldaki prim gününe göre ödenek süresi (gün). Şart sağlanmıyorsa 0."""
    hak = 0
    for esik, gun in ISSIZLIK_SURELERI:
        if prim_gun_son3yil >= esik:
            hak = gun
    return hak
