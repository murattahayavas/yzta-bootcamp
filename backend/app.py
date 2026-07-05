"""
HakKazan — Flask API (Sprint 1)

Endpointler:
  GET  /                → frontend (index.html)
  POST /api/yukle       → bordro/belge yükleme (Sprint 1: güvenli saklama;
                          otomatik bordro ayrıştırma Sprint 2 kapsamında)
  POST /api/hesapla     → çalışma bilgileri + soru → ajan hattı → sonuç JSON

Çalıştırma:  python app.py   (http://localhost:5000)
GEMINI_API_KEY tanımlı değilse Planner/Insight demo modunda çalışır;
hesap ve doğrulama tam doğruluktadır.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from core.calculations import CalismaBilgisi, AyrilisSekli
from graph.build import run

BASE = Path(__file__).resolve().parent
UPLOAD_DIR = BASE / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
IZINLI_UZANTILAR = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_BOYUT_MB = 10

app = Flask(__name__, static_folder=str(BASE.parent / "frontend"), static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = MAX_BOYUT_MB * 1024 * 1024
CORS(app)


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
    f.save(UPLOAD_DIR / f"{dosya_id}{uzanti}")
    return jsonify({
        "dosya_id": dosya_id,
        "mesaj": "Belge alındı. Otomatik bordro ayrıştırma Sprint 2'de devreye girecek; "
                 "şimdilik bilgileri formdan girmeye devam edin.",
    })


def _tarih(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


@app.post("/api/hesapla")
def hesapla():
    try:
        d = request.get_json(force=True)
        bilgi = CalismaBilgisi(
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
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"hata": f"Geçersiz girdi: {e}"}), 400

    if bilgi.cikis <= bilgi.ise_giris:
        return jsonify({"hata": "Çıkış tarihi, işe giriş tarihinden sonra olmalı."}), 400

    sonuc = run(bilgi, d.get("soru", ""))
    return jsonify({
        "sonuclar": {k: v.to_dict() for k, v in sonuc["sonuclar"].items()},
        "ihlaller": sonuc["ihlaller"],
        "aciklama": sonuc["aciklama"],
        "demo_mode": sonuc.get("demo_mode", False),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=os.environ.get("FLASK_DEBUG") == "1")
