"""
Critic ajanının deterministik doğrulama kuralları.

Felsefe: Critic, hesaplama kodunun İÇİNE bakmaz — çıktıyı BAĞIMSIZ
kurallarla sınar. Böylece hesap motorundaki bir bug'ı (ya da Sprint 2'de
LLM'in ürettiği bir hesabı) yakalayabilir. Bu, Reflexion döngüsünün
temelidir: check() başarısız olursa graph, hesaplamayı düzeltme
talimatıyla yeniden çalıştırır.
"""
from __future__ import annotations

from core import rules
from core.calculations import CalismaBilgisi, HesapSonucu


def check(b: CalismaBilgisi, sonuclar: dict[str, HesapSonucu]) -> list[str]:
    """Boş liste = geçti. Dolu liste = ihlal açıklamaları (Reflexion girdisi)."""
    v: list[str] = []
    gun = b.kidem_gun()

    k = sonuclar.get("kidem")
    if k and k.hak_var:
        tavan = rules.kidem_tavani(b.cikis)
        ust_sinir = tavan * (gun / 365) * 1.001  # yuvarlama payı
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

    # Hak tutarlılığı çapraz kontrolleri
    if k and k.hak_var and b.ayrilis.value == "istifa":
        v.append("TUTARLILIK: haklı neden olmadan istifada kıdem hakkı doğmamalı.")
    if z and z.hak_var and b.ayrilis.value in ("istifa", "emeklilik", "askerlik", "evlilik"):
        v.append("TUTARLILIK: bu ayrılış şeklinde işsizlik ödeneği bağlanmamalı.")

    return v
