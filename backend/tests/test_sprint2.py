"""Sprint 2 birim testleri — senaryo motoru, çapraz Critic, Planner sezgisi, hafıza, grafik."""
from datetime import date

from core.calculations import CalismaBilgisi, AyrilisSekli, hepsini_hesapla
from core.scenarios import senaryo_hesapla, senaryo_karsilastir
from core.validators import check_senaryo_tutarliligi
from agents.nodes import _heuristik_plan, _ay_ekle
from agents.charts import senaryo_grafigi
from graph.build import run


def _bilgi(**kw) -> CalismaBilgisi:
    base = dict(
        ise_giris=date(2021, 7, 5),
        cikis=date(2026, 7, 5),
        brut_maas=60_000.0,
        ayrilis=AyrilisSekli.ISVEREN_FESHI,
    )
    base.update(kw)
    return CalismaBilgisi(**base)


# ---------------------------------------------------------------- senaryo motoru
def test_senaryo_hesapla_tek():
    s = senaryo_hesapla(_bilgi(), AyrilisSekli.ISTIFA)
    assert s.ayrilis == "istifa"
    assert s.tek_seferlik_toplam == 0.0  # istifa: kıdem+ihbar hak yok


def test_senaryo_karsilastir_coklu():
    sonuclar = senaryo_karsilastir(_bilgi(), [AyrilisSekli.ISVEREN_FESHI, AyrilisSekli.ISTIFA, AyrilisSekli.IKALE])
    etiketler = {s.ayrilis for s in sonuclar}
    assert etiketler == {"isveren_feshi", "istifa", "ikale"}
    isveren = next(s for s in sonuclar if s.ayrilis == "isveren_feshi")
    istifa = next(s for s in sonuclar if s.ayrilis == "istifa")
    assert isveren.tek_seferlik_toplam > istifa.tek_seferlik_toplam


def test_ikale_kidem_ihbar_hak_yok():
    s = senaryo_hesapla(_bilgi(), AyrilisSekli.IKALE)
    assert not s.sonuclar["kidem"].hak_var
    assert not s.sonuclar["ihbar"].hak_var
    assert not s.sonuclar["issizlik"].hak_var


def test_ek_cikis_senaryosu_3_ay_sonra():
    b = _bilgi()
    sonuclar = senaryo_karsilastir(b, [b.ayrilis], ek_cikis_senaryosu=_ay_ekle(b.cikis, 3))
    assert len(sonuclar) == 2
    orijinal, gec = sonuclar[0], sonuclar[1]
    assert gec.cikis > orijinal.cikis
    assert gec.tek_seferlik_toplam >= orijinal.tek_seferlik_toplam - 1.0


# ------------------------------------------------------------ çapraz Critic
def test_capraz_critic_temiz_gecer():
    sonuclar = senaryo_karsilastir(_bilgi(), [AyrilisSekli.ISVEREN_FESHI, AyrilisSekli.ISTIFA, AyrilisSekli.IKALE])
    assert check_senaryo_tutarliligi(sonuclar) == []


def test_capraz_critic_istifa_ihlalini_yakalar():
    sonuclar = senaryo_karsilastir(_bilgi(), [AyrilisSekli.ISVEREN_FESHI, AyrilisSekli.ISTIFA])
    # Kasıtlı bozma: istifa toplamını işveren feshinden yüksek göster
    istifa = next(s for s in sonuclar if s.ayrilis == "istifa")
    istifa.tek_seferlik_toplam = 999_999.0
    ihlaller = check_senaryo_tutarliligi(sonuclar)
    assert any("SENARYO" in i for i in ihlaller)


def test_capraz_critic_ikale_hak_ihlalini_yakalar():
    sonuclar = senaryo_karsilastir(_bilgi(), [AyrilisSekli.IKALE])
    sonuclar[0].sonuclar["kidem"].hak_var = True  # kasıtlı bozma
    ihlaller = check_senaryo_tutarliligi(sonuclar)
    assert any("ikale" in i.lower() for i in ihlaller)


# --------------------------------------------------------------- Planner sezgisi
def test_planner_istifa_sorusu_algilar():
    plan = _heuristik_plan("İstifa edersem ne kaybederim?", AyrilisSekli.ISVEREN_FESHI, date(2026, 7, 5))
    assert plan["senaryo_karsilastirma"]
    assert "istifa" in plan["senaryolar"]


def test_planner_ikale_sorusu_algilar():
    plan = _heuristik_plan("İkale yapsam ne talep etmeliyim?", AyrilisSekli.ISVEREN_FESHI, date(2026, 7, 5))
    assert plan["senaryo_karsilastirma"]
    assert "ikale" in plan["senaryolar"]


def test_planner_ay_kalibini_algilar():
    plan = _heuristik_plan("3 ay daha çalışırsam ne değişir?", AyrilisSekli.ISVEREN_FESHI, date(2026, 7, 5))
    assert plan["ek_ay"] == 3


def test_planner_basit_soru_senaryo_tetiklemez():
    plan = _heuristik_plan("Kıdem tazminatım ne kadar?", AyrilisSekli.ISVEREN_FESHI, date(2026, 7, 5))
    assert not plan["senaryo_karsilastirma"]


def test_ay_ekle_yil_tasmasi():
    assert _ay_ekle(date(2026, 11, 15), 3) == date(2027, 2, 15)


# --------------------------------------------------------- uçtan uca (senaryo dalı)
def test_graph_senaryo_dali_demo_modu():
    sonuc = run(_bilgi(), soru="İstifa edersem ne kaybederim, işveren çıkarırsa ne alırım?")
    assert "senaryolar" in sonuc and len(sonuc["senaryolar"]) >= 2
    assert sonuc["grafik"] and sonuc["grafik"].startswith("data:image/png;base64,")
    assert sonuc["ihlaller"] == []


def test_graph_hafiza_takip_sorusu():
    gecmis = [{"soru": "Kıdem tazminatım ne kadar?", "aciklama": "Net kıdem tazminatınız 327.740 TL."}]
    sonuc = run(_bilgi(), soru="Peki ihbar ne kadar?", gecmis=gecmis)
    assert "aciklama" in sonuc  # hafıza state'e taşınmış, hata vermeden tamamlanmış


# --------------------------------------------------------------------- grafik
def test_grafik_data_uri_uretir():
    sonuclar = senaryo_karsilastir(_bilgi(), [AyrilisSekli.ISVEREN_FESHI, AyrilisSekli.ISTIFA])
    uri = senaryo_grafigi(sonuclar)
    assert uri.startswith("data:image/png;base64,") and len(uri) > 1000
