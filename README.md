# Yapay Zeka ve Teknoloji Akademisi — Bootcamp 2026

## 👥 Takım Bilgileri

| Üye | Rol |
|---|---|
| **Taha Yavaş** | Scrum Master & Backend Developer |
| **Zuhal Tuana Yıldırım** | Product Owner & AI Developer |
| **Mühire Alkan** | Frontend Developer & UI Designer |

---

## 🚀 Ürün Bilgileri

### Ürün İsmi
**HakKazan** — AI-Powered Multi-Agent Compensation Calculator

### Ürün Açıklaması
HakKazan; çalışanların en kritik sorularından biri olan **"İşten ayrılırsam ne
alırım?"** sorusuna yanıt veren, çoklu yapay zekâ ajanları (multi-agent)
mimarisiyle çalışan bir kıdem tazminatı, ihbar tazminatı ve işsizlik ödeneği
hesaplama platformudur.

Mevcut internet hesaplayıcılarından temel farkı **güvenilirlik yaklaşımıdır**:
HakKazan'da tutarlar yapay zekâya hesaplatılmaz. Para hesabı, güncel mevzuat
parametreleriyle çalışan deterministik bir Python motorunda yapılır; yapay zekâ
ajanları kullanıcının serbest metin sorusunu yorumlar ve doğrulanmış sonucu
sade Türkçeyle açıklar. Aradaki **Critic (Doğrulayıcı) ajanı** ise her sonucu
hesap kodundan bağımsız kurallarla (tavan aşımı, hak tutarlılığı,
net = brüt − kesinti) çapraz kontrolden geçirir — bir ihlal tespit edilirse
hesap otomatik olarak yeniden çalıştırılır (Reflexion döngüsü).

### 🛠️ Teknik Altyapı & Mimari

| Katman | Teknoloji |
|---|---|
| Backend | Python · **Flask API** (dosya yükleme, hesap motoru, ajan orkestrasyonu) |
| AI & Orkestrasyon | **LangGraph** (LangChain ekosistemi) · **Google Gemini** |
| Frontend | HTML5 · Tailwind CSS · Vanilla JavaScript |
| Test | pytest (14 birim + uçtan uca test) |

![HakKazan Multi-Agent Akış Şeması](docs/architecture.png)

**Şemanın izahı — akış soldan sağa şöyle işler:** Kullanıcı, frontend üzerinden
çalışma bilgilerini girer (isteğe bağlı belge yükler) ve serbest metinle sorusunu
sorar; Flask API bu isteği LangGraph orkestrasyon katmanına iletir.
**Planner Ajanı** (Gemini) soruyu yorumlayarak hangi kalemlerin (kıdem, ihbar,
işsizlik) hesaplanacağına karar verir. **Hesaplama Motoru** deterministik Python
fonksiyonlarıyla tutarları üretir — bu katmanda LLM yoktur, bu bilinçli bir
tasarım kararıdır: para hesabında olasılıksal model kullanılmaz. **Critic Ajanı**
sonuçları bağımsız doğrulama kurallarından geçirir; kırmızı okla gösterilen
geri dönüş kenarı Reflexion döngüsüdür — ihlal varsa hesap en fazla 3 kez
düzeltme talimatıyla yeniden çalıştırılır. Doğrulamadan geçen sonuç
**Insight Ajanı**na (Gemini) gider ve kullanıcının sorusuna doğrudan hitap eden
sade bir açıklamaya dönüştürülerek arayüze döner. Yeşil kutular LLM ajanlarını,
kırmızı kutular deterministik katmanları gösterir.

### ✨ Ürün Özellikleri (Sprint 1 itibarıyla)
* **Üç kalem tek ekranda:** Kıdem tazminatı, ihbar tazminatı ve işsizlik ödeneği
  — hak koşulları (1 yıl şartı, ayrılış şekline göre hak durumu, 600/900/1080
  prim günü eşikleri) otomatik denetlenir.
* **Dönemsel güncel mevzuat:** Kıdem tavanı (Tem–Ara 2026: 73.729,84 TL) ve
  brüt asgari ücret (2026: 33.030 TL) çıkış tarihine göre otomatik seçilir;
  yeni dönem açıklandığında tek dosyaya (`core/rules.py`) satır eklenir.
* **Çoklu ajan doğrulaması:** Hesap hatalarını yakalamak için tasarlanmış
  bağımsız Critic katmanı ve Reflexion (otomatik düzeltme) döngüsü.
* **Serbest metin soru:** "İstifa edersem ne kaybederim?" gibi sorular Planner
  ajanı tarafından yorumlanır.
* **Şeffaf hesap:** Her kalemin adım adım hesap dökümü ve yasal dayanak notları
  arayüzde gösterilir.
* **Belge yükleme altyapısı:** Bordro/belge güvenli şekilde alınır (PDF/PNG/JPG);
  otomatik bordro ayrıştırma (OCR) Sprint 2 kapsamındadır.

### 💰 Gelir Modeli (Small Bet)
Temel tek-kalem hesaplamalar ücretsiz; detaylı senaryo analizleri
("istifa vs çıkarılma", "3 ay daha çalışırsam ne değişir?"), karşılaştırmalı
tablolar ve tam PDF raporu premium modelle sunulacaktır.

### 🎯 Hedef Kitle
* Mevcut işinden ayrılmayı, istifa etmeyi veya ikale imzalamayı düşünen çalışanlar
* Haklarını tam ve doğru öğrenmek isteyen beyaz ve mavi yaka profesyoneller
* 18–65 yaş arası tüm sigortalı çalışanlar

---

## ⚙️ Kurulum ve Çalıştırma

```bash
pip install -r requirements.txt
cp .env.example .env          # GEMINI_API_KEY ekleyin (opsiyonel)
cd backend && python app.py   # http://localhost:5000
```

`GEMINI_API_KEY` tanımlı değilse uygulama **demo modunda** uçtan uca çalışır:
hesap ve doğrulama tam doğrulukta, açıklama şablonla üretilir.

**Testler:** `cd backend && python -m pytest tests/ -q`

---

## 📈 Proje Yönetimi & Ürün Durumu

### 📋 Sprint 1 — Backlog Düzeni ve Story Seçimleri

**Backlog Düzeni**

Product Backlog, proje kapsamındaki teknik bağımlılıklar dikkate alınarak
öncelik sırasına göre düzenlenmiştir. İlk aşamada sistemin temelini oluşturacak
veri yükleme altyapısı ve çoklu ajan mimarisi önceliklendirilmiş, bu yapı
tamamlandıktan sonra hesaplama ve analiz süreçlerine yönelik geliştirmelerin
yapılması planlanmıştır.

**Story Seçimi ve Sprint Kapasitesi**

Sprint 1 için ekip kapasitesi toplam **21 Story Point** olarak belirlenmiştir.
Sprint planlama toplantısında öncelikli ihtiyaçlar değerlendirilmiş ve bu
kapasiteyi aşmayacak şekilde ilk dört Product Backlog Item sprint kapsamına
alınmıştır.

**Risk Yönetimi**

Sprint planlaması yapılırken büyük ölçekli işlerin tek parça halinde
alınmamasına dikkat edilmiştir. En yüksek efora sahip olan "Multi-Agent Çekirdek
Mimarisi" çalışması **8 Story Point** olarak planlanmış ve sprint kapasitesinin
yarısını aşmayacak şekilde sınırlandırılmıştır. Böylece geliştirme sürecinin
daha kontrollü ilerlemesi, olası gecikmelerin önlenmesi ve gerektiğinde işlerin
daha küçük görevlere ayrılarak yönetilmesi hedeflenmiştir.

### 📊 Product Backlog URL
* 📄 [`docs/backlog_raporlari.pdf`](docs/backlog_raporlari.pdf)

### 💬 Sprint 1 Daily Scrum Notları
Sprint boyunca yapılan dört toplantının (22, 26, 30 Haziran ve 4 Temmuz)
kişi bazlı yapıldı/yapılacak/engel raporları:
* 📄 [`docs/toplanti_raporlari.pdf`](docs/toplanti_raporlari.pdf)

### 📌 Sprint 1 Board
*Sprint panosu Miro üzerinde tutulmaktadır. Mavi kartlar kullanıcı hikâyelerini
(Story), kırmızı kartlar teknik görevleri (Task) temsil eder.*
<!-- Pano ekran görüntüsü alınca: docs/board.png olarak kaydedip
     aşağıdaki satırın başındaki yorum işaretlerini kaldırın.
![Sprint 1 Board](docs/board.png)
-->

### 🖼️ Ürün Durumu (Sprint 1 kapanış ekran görüntüleri)

**Bilgi girişi ve belge yükleme ekranı** — sürükle-bırak yükleme alanı,
çalışma bilgileri formu ve serbest metin soru kutusu:

![Bilgi girişi ekranı](docs/ekran_form.png)

**Sonuç ekranı** — üç kalemin özet kartları ve Critic doğrulama rozeti
(demo modu bildirimiyle birlikte):

![Sonuç ekranı](docs/ekran_sonuc.png)

**Hesap adımları ve dayanaklar** — her kalemin adım adım dökümü, dönemsel
kıdem tavanı seçimi ve yasal dayanak notları:

![Hesap adımları ekranı](docs/ekran_adimlar.png)

### ✅ Sprint 1 Review

Sprint 1 süresince geliştirilen Flask API altyapısı, frontend dosya yükleme
ekranı prototipi ve LangGraph (LangChain ekosistemi) tabanlı çekirdek ajan
mimarisinin ilk çalışan sürümü değerlendirilmiş, tamamlanan çalışmalar gözden
geçirilmiş ve sistem test sonuçları incelenmiştir.

**Alınan Kararlar**

Kullanıcılardan toplanacak verilerin güvenli şekilde saklanması ve analiz
edilebilmesi amacıyla proje kapsamında bir veritabanı oluşturulmasına karar
verilmiştir. Yapılan değerlendirme sonucunda, ilk sprintte geliştirilen dosya
yükleme ve form ekranı için henüz veritabanı entegrasyonuna ihtiyaç olmadığı
görülmüştür. Bu nedenle veritabanı geliştirme çalışması Product Backlog'a
alınmış ve Sprint 2 kapsamında geliştirilmek üzere ertelenmiştir.

**Ürün Durumu**

Sprint sonunda gerçekleştirilen entegrasyon testlerinde, yüklenen bordro
belgelerinin Flask API üzerinden başarılı şekilde sisteme aktarıldığı ve elde
edilen verilerin Hesaplama Ajanı tarafından sorunsuz işlendiği görülmüştür.
Yapılan testlerde sistemin temel işlevlerini kararlı bir şekilde yerine
getirdiği doğrulanmıştır.

**Sonraki Sprint İçin Planlanan Çalışmalar**

Bir sonraki sprintte çoklu ajan yapısına gelişmiş senaryo analizleri
eklenecektir. Bunlar arasında istifa durumunda oluşabilecek hak kayıplarının
hesaplanması, belirli bir süre sonra işten ayrılma senaryolarının simülasyonu
ve premium PDF raporlama özelliğinin geliştirilmesi yer almaktadır.

**Sprint Review Katılımcıları**

* Taha Yavaş — Scrum Master
* Zuhal Tuana Yıldırım — Product Owner
* Mühire Alkan — Developer

### 🔄 Sprint 1 Retrospective

Sprint 1 tamamlandıktan sonra ekip, çalışma sürecini değerlendirerek sonraki
sprintlerde uygulanmak üzere aşağıdaki iyileştirme kararlarını almıştır.

**Görev Dağılımı**

İlk sprintteki iş yükü dağılımı değerlendirilmiş ve ekip üyeleri arasındaki
görevlerin daha dengeli planlanmasına karar verilmiştir. Böylece iş yükünün tek
bir kişide yoğunlaşmasının önüne geçilmesi hedeflenmektedir.

**Story Point Değerlendirmesi**

Görevler için verilen Story Point tahminlerinin bazı işlerde gerçek süreleri tam
olarak yansıtmadığı görülmüştür. Sonraki sprint planlamalarında geliştiricilerin
daha ayrıntılı geri bildirim vermesi ve tahminlerin ekip tarafından birlikte
değerlendirilmesi kararlaştırılmıştır.

**Kalite ve Test Süreci**

Çoklu ajan mimarisi ile tazminat hesaplama fonksiyonlarının doğruluğu projenin
en önemli bileşenleri arasında yer almaktadır. Bu nedenle kod kalitesini
artırmak ve olası hataları erken tespit edebilmek amacıyla birim testlerine daha
fazla zaman ayrılması ve test kapsamının genişletilmesi kararlaştırılmıştır.

### 🗺️ Sprint 2 Yol Haritası
* Senaryo analizi ve karşılaştırma ("istifa vs çıkarılma vs ikale")
* Otomatik bordro ayrıştırma (OCR) ve alanların ön-doldurulması
* Veritabanı entegrasyonu (Sprint 1 Review kararı)
* Kümülatif vergi matrahıyla tam ihbar neti
* Konuşma hafızası (takip soruları)
* Premium PDF raporlama

---

> ⚖️ HakKazan bilgilendirme amaçlıdır; hukuki veya mali danışmanlık değildir.
> Kesin tutarlar bordro kalemlerine ve SGK kayıtlarına göre değişebilir.
