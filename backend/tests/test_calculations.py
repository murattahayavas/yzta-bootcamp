"""Sprint 1 birim testleri — hesap motoru + Critic + graph uçtan uca (tekli)."""
from datetime import date

from core.calculations import CalismaBilgisi, AyrilisSekli, kidem_tazminati, ihbar_tazminati, issizlik_odenegi, hepsini_hesapla
from core.validators import check
from core import rules


def _bilgi(**kw) -> CalismaBilgisi:
    base = dict(
        ise_giris=date(2021, 7, 5),
        cikis=date(2026, 7, 5),
        brut_maas=60_000.0,
        ayrilis=AyrilisSekli.ISVEREN_FESHI,
    )
    base.update(kw)
    return CalismaBilgisi(**base)


def test_kidem_temel():
    s = kidem_tazminati(_bilgi())
    gun = _bilgi().kidem_gun()
    assert s.hak_var
    beklenen = round(60_000 * gun / 365, 2)
    assert abs(s.brut - beklenen) < 0.01
    assert s.net < s.brut


def test_kidem_tavan_uygulanir():
    s = kidem_tazminati(_bilgi(brut_maas=120_000.0))
    tavan = rules.kidem_tavani(date(2026, 7, 5))
    gun = _bilgi().kidem_gun()
    assert abs(s.brut - round(tavan * gun / 365, 2)) < 0.01


def test_kidem_donemsel_tavan():
    assert rules.kidem_tavani(date(2026, 6, 30)) == 64_948.77
    assert rules.kidem_tavani(date(2026, 7, 1)) == 73_729.84


def test_istifa_kidem_yok():
    assert not kidem_tazminati(_bilgi(ayrilis=AyrilisSekli.ISTIFA)).hak_var


def test_bir_yildan_az_kidem_yok():
    assert not kidem_tazminati(_bilgi(ise_giris=date(2026, 1, 10))).hak_var


def test_ihbar_haftalari():
    assert rules.ihbar_haftasi(100) == 2
    assert rules.ihbar_haftasi(200) == 4
    assert rules.ihbar_haftasi(600) == 6
    assert rules.ihbar_haftasi(2000) == 8


def test_ihbar_hesap():
    s = ihbar_tazminati(_bilgi())
    beklenen_brut = round(60_000 / 30 * 8 * 7, 2)
    assert s.hak_var and abs(s.brut - beklenen_brut) < 0.01
    assert "gelir_vergisi" in s.kesintiler


def test_ihbar_istifada_yok():
    assert not ihbar_tazminati(_bilgi(ayrilis=AyrilisSekli.ISTIFA)).hak_var


def test_issizlik_tavan():
    s = issizlik_odenegi(_bilgi(brut_maas=200_000.0))
    tavan = 33_030.0 * 0.80
    assert s.hak_var and abs(s.brut - tavan) < 0.01


def test_issizlik_sure_esikleri():
    assert rules.issizlik_gun(599) == 0
    assert rules.issizlik_gun(600) == 180
    assert rules.issizlik_gun(900) == 240
    assert rules.issizlik_gun(1080) == 300


def test_issizlik_istifada_yok():
    assert not issizlik_odenegi(_bilgi(ayrilis=AyrilisSekli.ISTIFA)).hak_var


def test_critic_temiz_gecer():
    b = _bilgi()
    assert check(b, hepsini_hesapla(b)) == []


def test_critic_bozuk_hesabi_yakalar():
    b = _bilgi()
    sonuclar = hepsini_hesapla(b)
    sonuclar["kidem"].brut = 10_000_000.0
    ihlaller = check(b, sonuclar)
    assert any("KIDEM" in i for i in ihlaller)


def test_graph_uctan_uca_demo_modu():
    from graph.build import run
    sonuc = run(_bilgi(), soru="ne alirim genel durumum?")
    assert "aciklama" in sonuc and sonuc["sonuclar"]["kidem"].hak_var
    assert sonuc["ihlaller"] == []
