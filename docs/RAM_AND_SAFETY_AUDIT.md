# Railway RAM + Safety/RAG/LangGraph Denetimi (Faz 4)

Bu doküman **analiz/rapordur**; üretim davranışı değiştirilmedi (ilke: önce ölç,
çalışan RAG/safety'i RAM için kaldırma). Ölçüm aracı: `scripts/memory_probe.py`
(salt tanı, prod'u etkilemez).

## 1. RAM kök-neden analizi

### Ölçüm (lokal Windows RSS — Railway Linux'a birebir değil, yönsel)
| Aşama | RSS | Δ |
|---|---|---|
| interpreter + psutil | ~19 MB | baseline |
| `import api` (app+router+langchain+chromadb+google-genai+PIL) | ~391 MB | +372 |
| `import graph` / `import memory` | ~391 MB | +0 (zaten yüklü) |
| **ilk klinik RAG sorgusu** | ~1019 MB | **+628** |
| image pipeline peak | +24 | transient |
| image ref bırak + gc | −8 | RSS tam düşmüyor |

### Kök neden (lokal ölçümle DOĞRULANAN + KESİNLEŞMEYEN)
1. **Baseline ~390MB (doğrulandı):** eager import maliyeti (langchain + chromadb + google-genai + PIL + fastapi). Sabit.
2. **+~628MB ilk RAG'de (DOĞRULANDI):** **lokal HuggingFace embedding modeli** (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`) + **torch runtime** + **Chroma koleksiyonu** belleğe yükleniyor (lazy singleton `_get_embeddings`, [src/memory.py:64](../src/memory.py); process ömrü boyunca kalıcı). Lokal ölçümde **kalıcı baseline artışının ana nedeni** olarak doğrulandı; "restart→~0.4GB, zamanla ~1.8–2.4GB'a yükselir" gözlemiyle tutarlı.
3. **4–4.5GB Railway spike'ları (KESİNLEŞMEDİ):** Bu spike'ların gerçek bir **leak** mi, **allocator high-water RSS** mi, yoksa **concurrency** transient'i mi olduğu **canlı Railway probe olmadan kesinleştirilemez**. Lokal image-pipeline ölçümü bitmap'in transient olduğunu ve gc sonrası RSS'in tam düşmediğini gösterdi (allocator davranışına işaret) — fakat kesin ayrım için Railway'de `memory_probe` çalıştırılmalı. Bu belirsizlik nedeniyle **RAM için kod optimizasyonu yapılmadı**.

### Doğrulanan yapı
- **Tek Uvicorn worker** (`--workers 1`, [scripts/start_railway.py](../scripts/start_railway.py)) → RAM **worker duplikasyonundan değil**.
- **Görsel içeriği LangGraph state'inde taşınmıyor** — state yalnız `profil_ozeti` (str), kısa `sohbet_gecmisi` (≤10), `hafiza`, snapshot payload. Görsel/base64 graph state'e girmiyor → graph state küçük.
- Image pipeline'da tek görselin eşzamanlı kopyaları: raw_bytes (~47KB) + base64 (~63KB) + decoded (~47KB) + PIL bitmap (~9MB, 2000×1500×3) + preview_b64 (~5KB). Bitmap dominant ama transient; işlem sonrası bırakılıyor. Media store preview'ı **700KB cap** ile küçük tutuyor.

### Öneriler (uygulanmadı — karar/ölçüm ister)
- **En büyük kaldıraç:** lokal MiniLM+torch (~600MB). Alternatif: Google embeddings API (`GoogleGenerativeAIEmbeddings`, `EMBEDDINGS_LOCAL_ONLY=false`) → torch+model RAM'den çıkar; **ama** API maliyeti/latency ekler ve retrieval kalitesi doğrulanmalı. **Bu turda değiştirilmedi.**
- **Düşük-riskli env mitigasyonu (kod değil):** Railway'de `MALLOC_ARENA_MAX=2` (glibc arena fragmentasyonunu azaltır) — spike sonrası RSS'i toparlamaya yardımcı olabilir.
- Baseline import'ları lazy'leştirmek marjinal ve riskli → önerilmez.

## 2. Safety flow denetimi (kod haritası)
| Katman | Nerede | Tür |
|---|---|---|
| Input prompt-injection | `_prompt_injection_warning` (chat.py) | deterministic keyword |
| Explicit food-suitability | `_explicit_input_safety_answer` → RuleEngine (chat.py) | **deterministic**, model öncesi |
| Üretilen cevap re-check | `_simple_chat_state` → `RuleEngine.check_rules(quality_profile, answer)` | **deterministic** backstop |
| Uydurma klinik eşik temizliği | `soften_unsourced_clinical_limits` | deterministic |
| Graph auditor | `denetleyici_node` (nodes.py) + RAG + "SAFE: NO" | LLM + RAG + kaynak-gate |
| Profil-çelişki notu | `_profile_conflict_answer` (chat.py) | deterministic |

- **Bypass:** Fast-path'ler (natural_fast_path, deterministic_intent, simple_response) graph'ı atlar **ama** üretilen cevap `_simple_chat_state` RuleEngine re-check'inden geçer → hiçbir yol food-suitability için **deterministic safety'yi tamamen bypass etmiyor**.
- **Duplikasyon:** RuleEngine birden çok noktada çağrılıyor (input/natural/tool) — aynı motor, çelişki yok; kabul edilebilir.
- **Prompt'a bağlı yüksek-risk:** `denetleyici_node`'un "SAFE: NO" kararı kısmen LLM'e dayanıyor; deterministic RuleEngine re-check backstop var. Kaynak yoksa RAG uyarı ekliyor, kesin konuşmuyor.
- **RAG-içi injection:** input-guardrail yalnız kullanıcı mesajını tarıyor; retrieved doküman içeriği instruction gibi işlenmiyor ama guardrail kapsamı dışında (korpus kürasyonlu → düşük risk). **Rapor edildi; büyük refactor yapılmadı.**

## 3. LangGraph maliyet/memory (telemetri ile)
- Graph turları `graph_used=1` + supervisor→triyaj→beslenme→denetleyici→şef zinciri + auditor RAG → tur başına **çok model çağrısı** (telemetri `request_id` ile toplar). Fast-path'ler `graph_used=0` (tek/az çağrı) — maliyet farkı artık ölçülebilir.
- State'te gereksiz büyük kopya (görsel/duplike profil) **yok**. `sohbet_gecmisi` ≤10 ile sınırlı. Minimal optimizasyon gerektiren belirgin bir israf bulunmadı → safety'ye dokunmadan değişiklik yapılmadı.

## 4. Kalan riskler
- RAM'in kalıcı ~1–2.4GB'ı embedding modeli/torch kaynaklı; kalıcı düşüş için embedding stratejisi kararı gerekir (maliyet/kalite tradeoff).
- Spike'lar allocator davranışı; `MALLOC_ARENA_MAX` env denemesi güvenli ilk adım.
- Bu bulgular lokal ölçüme dayanır; Railway Linux'ta mutlak değerler farklı olabilir — aynı `memory_probe` mantığı orada da çalıştırılabilir.
