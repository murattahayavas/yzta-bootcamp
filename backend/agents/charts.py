"""Senaryo karşılaştırma grafiği — Insight ajanının ürettiği görsel çıktı."""
from __future__ import annotations

import base64
from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def senaryo_grafigi(senaryolar: list) -> str:
    """senaryolar: SenaryoSonucu listesi. Döner: 'data:image/png;base64,...' data URI."""
    etiketler = [s.etiket for s in senaryolar]
    toplamlar = [s.tek_seferlik_toplam for s in senaryolar]
    issizlikler = [s.aylik_issizlik for s in senaryolar]

    fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=130)
    x = range(len(etiketler))
    bars = ax.bar(x, toplamlar, color="#2563EB", width=0.5, label="Tek seferlik toplam (kıdem+ihbar, net)")

    for xi, (bar, tutar) in enumerate(zip(bars, toplamlar)):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f"{tutar:,.0f} TL", ha="center", va="bottom", fontsize=9, fontweight="bold")

    ax2 = ax.twinx()
    ax2.plot(x, issizlikler, color="#DC2626", marker="o", linewidth=2, label="Aylık işsizlik ödeneği (net)")
    for xi, tutar in zip(x, issizlikler):
        if tutar > 0:
            ax2.annotate(f"{tutar:,.0f} TL/ay", (xi, tutar), textcoords="offset points",
                         xytext=(0, 10), ha="center", fontsize=8, color="#DC2626")

    ax.set_xticks(list(x))
    ax.set_xticklabels(etiketler, rotation=12, ha="right", fontsize=9)
    ax.set_ylabel("Tek seferlik toplam (TL)")
    ax2.set_ylabel("Aylık işsizlik ödeneği (TL)")
    ax.set_title("Senaryo Karşılaştırması", fontsize=12, fontweight="bold")

    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="upper center",
              bbox_to_anchor=(0.5, -0.25), ncol=1, fontsize=8, frameon=False)

    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"
