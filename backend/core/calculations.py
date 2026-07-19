"""
Deterministik hesaplama motoru.

Tasarım ilkesi: PARA HESABI LLM'E BIRAKILMAZ. Tüm tutarlar burada,
saf Python fonksiyonlarıyla hesaplanır. LLM ajanları yalnızca
(1) kullanıcının sorusunu yorumlar, (2) bu fonksiyonları araç olarak
çağırır, (3) sonucu açıklar. Critic ajanı da bu fonksiyonların
çıktısını bağımsız kurallarla doğrular.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from enum import Enum

from core import rules


class AyrilisSekli(str, Enum):
    ISVEREN_FESHI = "isveren_feshi"
    ISCI_HAKLI_FESIH = "isci_hakli_fesih"
    ISTIFA = "istifa"
    EMEKLILIK = "emeklilik"
    ASKERLIK = "askerlik"
    EVLILIK = "evlilik"
    ISVEREN_HAKLI_FESIH = "isveren_hakli_fesih"
    IKALE = "ikale"  # Sprint 2: karşılıklı sona erdirme (bozma) sözleşmesi


KIDEM_HAK_EDEN = {
    AyrilisSekli.ISVEREN_FESHI,
    AyrilisSekli.ISCI_HAKLI_FESIH,
    AyrilisSekli.EMEKLILIK,
    AyrilisSekli.ASKERLIK,
    AyrilisSekli.EVLILIK,
}

ISSIZLIK_HAK_EDEN = {
    AyrilisSekli.ISVEREN_FESHI,
    AyrilisSekli.ISCI_HAKLI_FESIH,
}

IHBAR_HAK_EDEN = {AyrilisSekli.ISVEREN_FESHI}

AYRILIS_ETIKETLERI = {
    AyrilisSekli.ISVEREN_FESHI: "İşveren feshi",
    AyrilisSekli.ISCI_HAKLI_FESIH: "İşçi haklı nedenle fesih",
    AyrilisSekli.ISTIFA: "İstifa",
    AyrilisSekli.EMEKLILIK: "Emeklilik",
    AyrilisSekli.ASKERLIK: "Askerlik",
    AyrilisSekli.EVLILIK: "Evlilik",
    AyrilisSekli.ISVEREN_HAKLI_FESIH: "İşveren haklı nedenle fesih (m.25/II)",
    AyrilisSekli.IKALE: "İkale (bozma sözleşmesi)",
}


@dataclass
class CalismaBilgisi:
    ise_giris: date
    cikis: date
    brut_maas: float
    yan_haklar_aylik: float = 0.0
    ayrilis: AyrilisSekli = AyrilisSekli.ISVEREN_FESHI
    ihbar_suresi_kullandirildi: bool = False
    vergi_dilimi: float = 0.15
    prim_gun_son3yil: int | None = None
    son120gun_calisti: bool = True

    def kidem_gun(self) -> int:
        return (self.cikis - self.ise_giris).days + 1

    def giydirilmis_aylik(self) -> float:
        return self.brut_maas + self.yan_haklar_aylik

    def kopya(self, **degisiklikler) -> "CalismaBilgisi":
        veri = asdict(self)
        veri["ayrilis"] = AyrilisSekli(veri["ayrilis"])
        veri.update(degisiklikler)
        return CalismaBilgisi(**veri)


@dataclass
class HesapSonucu:
    kalem: str
    hak_var: bool = False
    brut: float = 0.0
    kesintiler: dict = field(default_factory=dict)
    net: float = 0.0
    adimlar: list = field(default_factory=list)
    notlar: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _r2(x: float) -> float:
    return round(x, 2)


def kidem_tazminati(b: CalismaBilgisi) -> HesapSonucu:
    s = HesapSonucu(kalem="kidem")
    gun = b.kidem_gun()
    s.adimlar.append(f"Kıdem süresi: {gun} gün ({gun/365:.2f} yıl)")

    if gun < 365:
        s.hak_var = False
        s.notlar.append("Kıdem tazminatı için en az 1 yıl (365 gün) çalışma şartı sağlanmıyor.")
        return s
    if b.ayrilis == AyrilisSekli.IKALE:
        s.hak_var = False
        s.notlar.append(
            "İkale (bozma) sözleşmesinde kıdem tazminatı yasal bir hak değildir; "
            "işverenin sunduğu 'makul yarar' pazarlık konusudur. Aşağıdaki tutar, "
            "işveren feshi olsaydı doğacak referans tutardır."
        )
        return s
    if b.ayrilis not in KIDEM_HAK_EDEN:
        s.hak_var = False
        s.notlar.append(
            "Bu ayrılış şeklinde (haklı neden olmadan istifa / işverenin m.25-II haklı feshi) "
            "kıdem tazminatı hakkı doğmaz."
        )
        return s

    s.hak_var = True
    tavan = rules.kidem_tavani(b.cikis)
    giydirilmis = b.giydirilmis_aylik()
    esas_ucret = min(giydirilmis, tavan)
    s.adimlar.append(f"Giydirilmiş aylık brüt ücret: {_r2(giydirilmis)} TL")
    s.adimlar.append(f"Kıdem tavanı ({b.cikis.isoformat()} dönemi): {_r2(tavan)} TL")
    if giydirilmis > tavan:
        s.notlar.append("Giydirilmiş ücret tavanı aştığı için hesapta tavan tutarı esas alındı.")
    s.adimlar.append(f"Hesaba esas aylık ücret: {_r2(esas_ucret)} TL")

    brut = esas_ucret * (gun / 365)
    s.brut = _r2(brut)
    s.adimlar.append(f"Brüt kıdem = {_r2(esas_ucret)} × ({gun}/365) = {s.brut} TL")

    damga = _r2(brut * rules.DAMGA_VERGISI_ORANI)
    s.kesintiler = {"damga_vergisi": damga}
    s.net = _r2(brut - damga)
    s.adimlar.append(f"Damga vergisi (binde 7,59): −{damga} TL → Net: {s.net} TL")
    s.notlar.append("Kıdem tazminatı (tavan dahilinde) gelir vergisinden istisnadır; yalnızca damga vergisi kesilir.")
    return s


def ihbar_tazminati(b: CalismaBilgisi) -> HesapSonucu:
    s = HesapSonucu(kalem="ihbar")
    if b.ayrilis == AyrilisSekli.IKALE:
        s.hak_var = False
        s.notlar.append("İkale sözleşmesinde ihbar tazminatı da yasal zorunluluk değildir; pazarlık konusudur.")
        return s
    if b.ayrilis not in IHBAR_HAK_EDEN:
        s.hak_var = False
        s.notlar.append("İhbar tazminatı, işverenin bildirim süresi vermeden feshinde işçiye ödenir; bu ayrılış şeklinde hak doğmaz.")
        return s
    if b.ihbar_suresi_kullandirildi:
        s.hak_var = False
        s.notlar.append("İhbar süresi kullandırıldığı için ayrıca ihbar tazminatı ödenmez.")
        return s

    s.hak_var = True
    gun = b.kidem_gun()
    hafta = rules.ihbar_haftasi(gun)
    giydirilmis_gunluk = b.giydirilmis_aylik() / 30
    brut = giydirilmis_gunluk * hafta * 7
    s.brut = _r2(brut)
    s.adimlar.append(f"Kıdeme göre ihbar süresi: {hafta} hafta")
    s.adimlar.append(f"Giydirilmiş günlük ücret: {_r2(giydirilmis_gunluk)} TL")
    s.adimlar.append(f"Brüt ihbar = {_r2(giydirilmis_gunluk)} × {hafta}×7 gün = {s.brut} TL")

    gv = _r2(brut * b.vergi_dilimi)
    damga = _r2(brut * rules.DAMGA_VERGISI_ORANI)
    s.kesintiler = {"gelir_vergisi": gv, "damga_vergisi": damga}
    s.net = _r2(brut - gv - damga)
    s.adimlar.append(
        f"Gelir vergisi (%{int(b.vergi_dilimi*100)} dilim): −{gv} TL, "
        f"damga: −{damga} TL → Net: {s.net} TL"
    )
    s.notlar.append(
        "İhbar tazminatı gelir vergisine tabidir; net tutar, seçtiğiniz marjinal vergi dilimine "
        "göre yaklaşık hesaplanmıştır (kümülatif matrah tam bordro hesabı sonraki geliştirmede planlanmaktadır)."
    )
    return s


def issizlik_odenegi(b: CalismaBilgisi) -> HesapSonucu:
    s = HesapSonucu(kalem="issizlik")

    if b.ayrilis == AyrilisSekli.IKALE:
        s.hak_var = False
        s.notlar.append(
            "İkale ile ayrılan işçi, Yargıtay içtihadına göre 'kendi isteğiyle işten ayrılmış' "
            "sayıldığından kural olarak işsizlik ödeneğine hak kazanamaz."
        )
        return s
    if b.ayrilis not in ISSIZLIK_HAK_EDEN:
        s.hak_var = False
        s.notlar.append("İşsizlik ödeneği 'kendi istek ve kusuru dışında' işsiz kalanlara bağlanır; bu ayrılış şeklinde hak doğmaz.")
        return s
    if not b.son120gun_calisti:
        s.hak_var = False
        s.notlar.append("Fesihten önceki son 120 gün hizmet akdine tabi olma şartı sağlanmıyor.")
        return s

    prim = b.prim_gun_son3yil
    if prim is None:
        prim = min(b.kidem_gun(), 3 * 360)
        s.notlar.append(f"Son 3 yıl prim günü girilmediği için kıdem süresinden tahmin edildi: {prim} gün.")

    odenek_gun = rules.issizlik_gun(prim)
    if odenek_gun == 0:
        s.hak_var = False
        s.notlar.append("Son 3 yılda en az 600 gün prim şartı sağlanmıyor.")
        return s

    s.hak_var = True
    gunluk_brut = b.brut_maas / 30
    aylik = gunluk_brut * 30 * rules.ISSIZLIK_ODENEK_ORANI
    tavan = rules.asgari_ucret_brut(b.cikis) * rules.ISSIZLIK_TAVAN_ORANI
    s.adimlar.append(f"Son 4 ay ort. günlük brüt (son maaş varsayımı): {_r2(gunluk_brut)} TL")
    s.adimlar.append(f"Aylık ödenek (brüt %40): {_r2(aylik)} TL, tavan (asgari brütün %80'i): {_r2(tavan)} TL")
    if aylik > tavan:
        aylik = tavan
        s.notlar.append("Hesaplanan ödenek tavanı aştığı için tavan tutarı bağlanır.")

    s.brut = _r2(aylik)
    damga = _r2(aylik * rules.DAMGA_VERGISI_ORANI)
    s.kesintiler = {"damga_vergisi": damga}
    s.net = _r2(aylik - damga)
    s.adimlar.append(f"Damga vergisi: −{damga} TL → Aylık net ödenek: {s.net} TL")
    s.adimlar.append(f"Ödenek süresi: {odenek_gun} gün ({odenek_gun//30} ay) — prim: {prim} gün")
    s.notlar.append(f"Toplam ödenek (yaklaşık): {_r2(s.net * odenek_gun / 30)} TL ({odenek_gun} gün boyunca)")
    return s


def hepsini_hesapla(b: CalismaBilgisi) -> dict[str, HesapSonucu]:
    return {
        "kidem": kidem_tazminati(b),
        "ihbar": ihbar_tazminati(b),
        "issizlik": issizlik_odenegi(b),
    }


def tek_seferlik_toplam(sonuclar: dict[str, HesapSonucu]) -> float:
    """Kıdem + ihbar net toplamı (işsizlik aylık ödendiği için hariç tutulur)."""
    return round(sonuclar["kidem"].net + sonuclar["ihbar"].net, 2)
