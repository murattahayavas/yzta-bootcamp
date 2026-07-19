"""
HakKazan — Flask API (Sprint 2)

Endpointler:
  GET  /                → frontend (index.html)
  POST /api/yukle       → bordro/belge yükleme (PDF/PNG/JPG: saklanır;
                          XLSX: satır bazlı ayrıştırılıp alan önerisi döner)
  POST /api/hesapla     → çalışma bilgileri + soru + (opsiyonel) oturum geçmişi
                          → ajan hattı (tekli ya da senaryo dalı) → sonuç JSON

Sprint 2 yenilikleri:
  - Konuşma hafızası: `oturum_id` ile son N tur backend'de tutulur, takip
    sorularında Insight ajanına bağlam olarak geçirilir.
  - Basit Excel ayrıştırma: yaygın başlıkları (brüt ücret, işe giriş tarihi)
    tanıyıp formu ön-dolduracak alanlar döner (tam OCR değildir, dürüstçe
    "öneri" olarak sunulur).
"""
from __future__ import annotations

import os
import uuid
from collections import defaultdict, deque
from datetime import date, datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from core.calculations import CalismaBilgisi, AyrilisSekli
from graph.build import run

BASE = Path(__file__).resolve().parent
UPLOAD_DIR = BASE / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
IZINLI_UZANTILAR = {".pdf", ".png", ".jpg", ".jpeg", ".xlsx"}
MAX_BOYUT_MB = 10
HAFIZA_DERINLIGI = 5  # oturum başına saklanan son tur sayısı

app = Flask(__name__, static_folder=str(BASE.parent / "frontend"), static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = MAX_BOYUT_MB * 1024 * 1024
CORS(app)

# Basit bellek-içi oturum hafızası (Sprint 2 kapsamı; kalıcı depolama — veritabanı
# entegrasyonu — Sprint 1 Review kararınca sonraki geliştirmeye bırakılmıştır).
_OTURUMLAR: dict[str, deque] = defaultdict(lambda: deque(maxlen=HAFIZA_DERINLIGI))


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.post("/api/yukle")
def yukle():
    if "dosya" not in request.files:
        return jsonify({"hata": "Dosya bulunamadı (form alanı: 'dosya')."}), 400
    f = request.files["dosya"]
    uzanti = Path(f.filename or "").suffix.lower()
    if uzanti not in IZINLI_UZANTILAR:
        return jsonify({"hata": f"İzin verilen türler: {', '.join(sorted(IZINLI_UZANTILAR))}"}), 400

    dosya_id = uuid.uuid4().hex
    yol = UPLOAD_DIR / f"{dosya_id}{uzanti}"
    f.save(yol)

    if uzanti == ".xlsx":
        oneriler = _excel_alanlarini_cikar(yol)
        return jsonify({
            "dosya_id": dosya_id,
            "mesaj": "Excel dosyası okundu. Aşağıdaki alanlar otomatik önerildi; "
                     "lütfen kontrol edip onaylayın.",
            "onerilen_alanlar": oneriler,
        })

    return jsonify({
        "dosya_id": dosya_id,
        "mesaj": "Belge alındı. PDF/görsel belgelerden otomatik alan çıkarımı "
                 "(OCR) sonraki geliştirme kapsamındadır; şimdilik bilgileri "
                 "formdan girmeye devam edin.",
    })


def _excel_alanlarini_cikar(yol: Path) -> dict:
    """Yaygın bordro başlıklarını tanıyıp alan önerisi döner. Bulunamazsa
    ilgili anahtar sonuçta yer almaz — sahte/varsayılan değer üretilmez."""
    import openpyxl
    oneriler: dict = {}
    try:
        wb = openpyxl.load_workbook(yol, data_only=True)
        ws = wb.active
        etiket_haritasi = {
            "brüt ücret": "brut_maas", "brut ucret": "brut_maas", "brüt maaş": "brut_maas",
            "işe giriş": "ise_giris", "ise giris": "ise_giris",
        }
        for row in ws.iter_rows(max_row=100):
            for i, hucre in enumerate(row):
                if not isinstance(hucre.value, str):
                    continue
                anahtar = _tr_lower(hucre.value.strip())
                for etiket, alan in etiket_haritasi.items():
                    if etiket in anahtar and i + 1 < len(row):
                        komsu = row[i + 1].value
                        if komsu not in (None, ""):
                            oneriler[alan] = str(komsu)
    except Exception:
        pass  # Ayrıştırma başarısız olursa boş öneri döner; hata kullanıcıyı engellemez
    return oneriler


def _tr_lower(metin: str) -> str:
    return metin.replace("İ", "i").replace("I", "ı").lower()


def _tarih(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _bilgiden_parse(d: dict) -> CalismaBilgisi:
    return CalismaBilgisi(
        ise_giris=_tarih(d["ise_giris"]),
        cikis=_tarih(d["cikis"]),
        brut_maas=float(d["brut_maas"]),
        yan_haklar_aylik=float(d.get("yan_haklar_aylik", 0)),
        ayrilis=AyrilisSekli(d.get("ayrilis", "isveren_feshi")),
        ihbar_suresi_kullandirildi=bool(d.get("ihbar_suresi_kullandirildi", False)),
        vergi_dilimi=float(d.get("vergi_dilimi", 0.15)),
        prim_gun_son3yil=d.get("prim_gun_son3yil"),
        son120gun_calisti=bool(d.get("son120gun_calisti", True)),
    )


@app.post("/api/hesapla")
def hesapla():
    try:
        d = request.get_json(force=True)
        bilgi = _bilgiden_parse(d)
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"hata": f"Geçersiz girdi: {e}"}), 400

    if bilgi.cikis <= bilgi.ise_giris:
        return jsonify({"hata": "Çıkış tarihi, işe giriş tarihinden sonra olmalı."}), 400

    oturum_id = d.get("oturum_id") or ""
    gecmis = list(_OTURUMLAR[oturum_id]) if oturum_id else []
    soru = d.get("soru", "")

    sonuc = run(bilgi, soru, gecmis=gecmis)

    if oturum_id:
        _OTURUMLAR[oturum_id].append({"soru": soru, "aciklama": sonuc["aciklama"]})

    yanit = {
        "ihlaller": sonuc["ihlaller"],
        "aciklama": sonuc["aciklama"],
        "demo_mode": sonuc.get("demo_mode", False),
        "grafik": sonuc.get("grafik"),
    }
    if sonuc.get("senaryolar"):
        yanit["senaryolar"] = [s.to_dict() for s in sonuc["senaryolar"]]
    else:
        yanit["sonuclar"] = {k: v.to_dict() for k, v in sonuc["sonuclar"].items()}

    return jsonify(yanit)


@app.post("/api/oturum-sifirla")
def oturum_sifirla():
    oturum_id = (request.get_json(force=True) or {}).get("oturum_id", "")
    _OTURUMLAR.pop(oturum_id, None)
    return jsonify({"tamam": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=os.environ.get("FLASK_DEBUG") == "1")
