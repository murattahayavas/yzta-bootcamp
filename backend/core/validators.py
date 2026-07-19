"""
Critic ajanının deterministik doğrulama kuralları.

Sprint 1: tekli hesap doğrulaması (check).
Sprint 2: senaryo karşılaştırmalarında SENARYOLAR ARASI tutarlılık doğrulaması
(check_senaryo_tutarliligi) eklendi — bu, Reflexion döngüsünün ilk kez
gerçek bir ihtiyaca karşılık geldiği yerdir: LLM'in ürettiği bir senaryo
etiketi/eşleştirmesi yanlışsa (örn. "istifa" senaryosunu "işveren feshi"
etiketiyle karıştırırsa), çapraz kural bunu yakalar.
"""
from __future__ import annotations

from core import rules
from core.calculations import CalismaBilgisi, HesapSonucu, AyrilisSekli, KIDEM_HAK_EDEN, ISSIZLIK_HAK_EDEN


def check(b: CalismaBilgisi, sonuclar: dict[str, HesapSonucu]) -> list[str]:
    """Boş liste = geçti. Dolu liste = ihlal açıklamaları (Reflexion girdisi)."""
    v: list[str] = []
    gun = b.kidem_gun()

    k = sonuclar.get("kidem")
    if k and k.hak_var:
        tavan = rules.kidem_tavani(b.cikis)
        ust_sinir = tavan * (gun / 365) * 1.001
        if k.brut > ust_sinir:
            v.append(f"KIDEM: brüt ({k.brut}) tavan üst sınırını ({ust_sinir:.2f}) aşıyor.")
        if k.brut < 0 or k.net < 0:
            v.append("KIDEM: negatif tutar.")
        if k.net > k.brut:
            v.append("KIDEM: net, brütten büyük olamaz.")
        if gun < 365:
            v.append("KIDEM: 1 yıldan az kıdeme tazminat hesaplanmış.")
        beklenen_net = k.brut - sum(k.kesintiler.values())
        if abs(beklenen_net - k.net) > 0.05:
            v.append("KIDEM: net ≠ brüt − kesintiler.")

    i = sonuclar.get("ihbar")
    if i and i.hak_var:
        hafta = rules.ihbar_haftasi(gun)
        if hafta not in (2, 4, 6, 8):
            v.append(f"IHBAR: geçersiz ihbar haftası ({hafta}).")
        beklenen_brut = (b.giydirilmis_aylik() / 30) * hafta * 7
        if abs(beklenen_brut - i.brut) > 1.0:
            v.append(f"IHBAR: brüt ({i.brut}) bağımsız hesapla ({beklenen_brut:.2f}) uyuşmuyor.")
        if i.net > i.brut or i.net < 0:
            v.append("IHBAR: net tutar tutarsız.")

    z = sonuclar.get("issizlik")
    if z and z.hak_var:
        tavan = rules.asgari_ucret_brut(b.cikis) * rules.ISSIZLIK_TAVAN_ORANI
        if z.brut > tavan * 1.001:
            v.append(f"ISSIZLIK: aylık ödenek ({z.brut}) tavanı ({tavan:.2f}) aşıyor.")
        if z.net > z.brut or z.net < 0:
            v.append("ISSIZLIK: net tutar tutarsız.")

    if k and k.hak_var and b.ayrilis.value == "istifa":
        v.append("TUTARLILIK: haklı neden olmadan istifada kıdem hakkı doğmamalı.")
    if z and z.hak_var and b.ayrilis.value in ("istifa", "emeklilik", "askerlik", "evlilik", "ikale"):
        v.append("TUTARLILIK: bu ayrılış şeklinde işsizlik ödeneği bağlanmamalı.")
    if b.ayrilis.value == "ikale" and k and k.hak_var:
        v.append("TUTARLILIK: ikale senaryosunda kıdem yasal hak olarak gösterilmemeli.")

    return v


def check_senaryo_tutarliligi(senaryolar: list) -> list[str]:
    """
    Sprint 2: birden çok senaryonun (SenaryoSonucu listesi) birbirine göre
    mantıklı olup olmadığını denetler. Her senaryonun kendi iç tutarlılığı
    zaten check() ile denetlenmiştir; burada SENARYOLAR ARASI ilişkiler
    sınanır.
    """
    v: list[str] = []
    by_ayrilis = {s.ayrilis: s for s in senaryolar}

    # İkale senaryosunda kıdem/ihbar 'hak_var' False olmalı (yasal zorunluluk yok).
    # Bu kontrol tek senaryolu listelerde de geçerlidir, bu yüzden erken dönüş yapılmaz.
    if "ikale" in by_ayrilis:
        ikale = by_ayrilis["ikale"]
        if ikale.sonuclar["kidem"].hak_var or ikale.sonuclar["ihbar"].hak_var:
            v.append("SENARYO: ikale senaryosunda kıdem/ihbar yasal hak olarak işaretlenmemeli.")

    if len(senaryolar) < 2:
        return v

    # 1) İstifa, her zaman en düşük (ya da eşit) tek seferlik toplamı vermeli —
    #    çünkü istifada kıdem/ihbar hakkı doğmaz.
    if "istifa" in by_ayrilis:
        istifa_toplam = by_ayrilis["istifa"].tek_seferlik_toplam
        for ayrilis, s in by_ayrilis.items():
            if ayrilis == "istifa":
                continue
            if ayrilis in ("isveren_feshi", "isci_hakli_fesih") and s.tek_seferlik_toplam < istifa_toplam:
                v.append(
                    f"SENARYO: '{s.etiket}' toplamı ({s.tek_seferlik_toplam}) istifa toplamından "
                    f"({istifa_toplam}) düşük olamaz — istifada yasal hak doğmaz."
                )

    # 2) Aynı ayrılış şekli farklı çıkış tarihleriyle karşılaştırılıyorsa
    #    ("3 ay daha çalışırsam"), daha uzun kıdem daha düşük tek seferlik
    #    toplam vermemeli (kıdem tavanı aşılmadığı sürece monoton artmalı).
    cikis_gruplari: dict[str, list] = {}
    for s in senaryolar:
        cikis_gruplari.setdefault(s.ayrilis, []).append(s)
    for ayrilis, grup in cikis_gruplari.items():
        if len(grup) < 2:
            continue
        grup_sirali = sorted(grup, key=lambda s: s.cikis)
        for onceki, sonraki in zip(grup_sirali, grup_sirali[1:]):
            if sonraki.tek_seferlik_toplam < onceki.tek_seferlik_toplam - 1.0:
                v.append(
                    f"SENARYO: aynı ayrılış şeklinde daha geç çıkış tarihi ({sonraki.cikis}) "
                    f"daha düşük toplam ({sonraki.tek_seferlik_toplam}) veriyor — tavan aşımı dışında beklenmez."
                )

    return v
