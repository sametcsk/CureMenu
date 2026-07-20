# Dependency Security

Son doğrulama: 20 Temmuz 2026

## Temiz Ortam Provası

Bağımlılıklar, mevcut proje `.venv` ortamı değiştirilmeden Git dışındaki aşağıdaki
geçici sanal ortamda yeniden kurulup doğrulandı:

- Geçici venv: `C:\tmp\curemenu-dependency-rehearsal-20260720_211655`
- Python: `3.12.13`
- Kaynak: `requirements-dev.txt`
- Kurulum sonucu: başarılı
- `pip check`: `No broken requirements found`
- `opencv-python`: kurulmadı
- `opencv-python-headless`: `5.0.0.93`

Playwright Python bağımlılığı kuruldu; bu prova kapsamında Playwright browser
binary kurulumu yapılmadı.

## pip-audit Sonuçları

Denetimler hem temiz ortamda kurulu paketlere hem de requirements dosyalarına
ayrı ayrı uygulandı.

| Denetim | Sonuç |
|---|---|
| Kurulu temiz ortam | `chromadb 1.5.9 / PYSEC-2026-311` ve geçici venv'in paket yönetim aracı olan `pip 25.0.1` için advisory kayıtları |
| `requirements.txt` | `chromadb 1.5.9 / PYSEC-2026-311` |
| `requirements-dev.txt` | `chromadb 1.5.9 / PYSEC-2026-311` |

Uygulamanın runtime bağımlılık listesinde doğrulanan tek advisory
`chromadb 1.5.9 / PYSEC-2026-311` oldu. `pip 25.0.1` bulguları uygulama runtime
paketi değil, temiz geçici venv'i yöneten paket kurulum aracına aittir.

`pip-audit`, ChromaDB bulgusu için düzeltilmiş bir sürüm bildirmedi. Bu nedenle
kör bir major/minor upgrade yapılmayacaktır. Upstream düzeltme takip edilecek;
düzeltme yayımlandığında mevcut Chroma privacy, RAG, readiness ve regression
testleriyle kontrollü biçimde değerlendirilecektir.

## ChromaDB Çalıştırma Sınırı

ChromaDB HTTP server internete veya güvenilmeyen bir ağa açılmamalıdır. Mevcut
kapalı beta yaklaşımında Chroma yalnızca uygulamanın yerel/özel persistence
katmanı olarak tutulmalı; ağ üzerinden sunulması gerekirse kimlik doğrulama,
ağ izolasyonu, TLS ve sürüm düzeltmesi ayrıca doğrulanmadan yayınlanmamalıdır.

## Kalan Aksiyonlar

1. `PYSEC-2026-311` için ChromaDB upstream duyurularını ve fixed version bilgisini
   takip et.
2. Fixed version yayımlandığında ayrı bir geçici ortamda kurulum ve tam regression
   testi yap.
3. Yeni build ortamlarında paket yönetim aracını güncel ve denetlenmiş sürümde
   tut.
4. Tekrarlanabilir kurulum için doğrulanmış bir constraints/lock yaklaşımını ayrı
   ve kontrollü bakım turunda değerlendir.

Bu kayıt yalnızca bilinen advisory veritabanıyla yapılan teknik denetimi gösterir;
tam güvenlik veya klinik doğrulama garantisi değildir.
