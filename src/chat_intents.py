import re
import unicodedata

from src.medical_knowledge.normalizer import extract_medication_mentions, normalize_text
from src.profile_context import ResolvedProfileSnapshot


def normalized_message(message: str) -> str:
    text = (message or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.replace("ı", "i")


def _profile_has(values: tuple[str, ...], *needles: str) -> bool:
    haystack = normalized_message(" ".join(values))
    return any(normalized_message(needle) in haystack for needle in needles)


def _profile_bullets(snapshot: ResolvedProfileSnapshot) -> list[str]:
    bullets: list[str] = []
    if _profile_has(snapshot.diseases, "çölyak", "celiac", "gluten"):
        bullets.append("Çölyak kaydınız nedeniyle glutensiz içerik ve çapraz bulaş riski dikkate alınır.")
    if snapshot.allergies:
        bullets.append("Kayıtlı alerjileriniz öneride alerjen elemesi için kullanılır: " + ", ".join(snapshot.allergies) + ".")
    if _profile_has(snapshot.diseases, "diyabet", "diabetes"):
        bullets.append("Diyabet kaydınız nedeniyle ilave şeker, lif ve karbonhidrat dengesi kontrol edilir.")
    if _profile_has(snapshot.diseases, "ibs", "irritabl"):
        bullets.append("IBS kaydınız nedeniyle gaz/şişkinlik yapabilen içeriklerde tolerans takibi önerilir.")
    if _profile_has(snapshot.medications, "levotiroksin", "levothyroxine"):
        bullets.append("Levotiroksin kaydınız nedeniyle öğün ve ilaç zamanlaması için kısa uyarı eklenir.")
    if _profile_has(snapshot.medications, "warfarin", "coumadin"):
        bullets.append("Warfarin kaydınız varsa K vitamini içeren besinlerde tutarlılık ilkesi hatırlatılır.")
    return bullets


def _product_info_answer() -> str:
    return (
        "Ben CureBot, CureMenu'nün beslenme karar desteği asistanıyım. Yanıt hazırlarken seçtiğiniz "
        "kişinin hastalık, alerji, ilaç, hedef, tercih ve varsa tahlil bilgilerini birlikte değerlendiririm. "
        "Böylece genel bir liste vermek yerine o kişi için daha uygun seçenekleri daraltabilirim.\n\n"
        "CureMenu'de haftalık plan hazırlayabilir, tahlil yükleyebilir, menü veya buzdolabı fotoğrafını "
        "inceletebilir ve alışveriş listesiyle yaklaşık bütçe oluşturabilirsiniz. Tanı koymam veya tedavi "
        "düzenlemem; belirsiz ya da ilaçla ilgili bir durumda sağlık profesyoneline danışmanızı öneririm."
    )


def _product_trust_answer() -> str:
    return (
        "Sorunuzu önce seçtiğiniz kişinin profili ve konuşmanın bağlamıyla birlikte anlarım. Önerdiğim "
        "yemeklerin malzemelerini kayıtlı alerji ve beslenme kısıtlarıyla karşılaştırır, ilgili olduğunda "
        "ilaç ve tahlil bilgisini de dikkate alırım. Bilmediğim bir ayrıntıyı varmış gibi kabul etmem.\n\n"
        "Bu kontroller hata ihtimalini azaltır ama tamamen ortadan kaldırmaz. CureMenu tanı koymaz, tedavi "
        "düzenlemez ve doktor ya da diyetisyenin yerini almaz. İlaç, yeni belirti veya tahlil değişikliği "
        "içeren kararlarda sağlık profesyonelinizin önerisini izlemelisiniz."
    )


def _safe_breakfast_answer(snapshot: ResolvedProfileSnapshot) -> str:
    notes = []
    if _profile_has(snapshot.diseases, "\u00e7\u00f6lyak", "celiac", "gluten"):
        notes.append("glutensiz sertifikal\u0131 \u00fcr\u00fcnleri tercih edin")
    if _profile_has(snapshot.diseases, "diyabet", "diabetes"):
        notes.append("meyve ve tah\u0131l porsiyonunu \u00f6l\u00e7\u00fcl\u00fc tutun")
    if _profile_has(snapshot.diseases, "b\u00f6brek", "renal", "ckd"):
        notes.append("protein porsiyonunu takip eden uzman\u0131n\u0131zla netle\u015ftirin")
    if _profile_has(snapshot.medications, "levotiroksin", "levothyroxine"):
        notes.append("levotiroksin zamanlamas\u0131 i\u00e7in re\u00e7ete/eczac\u0131 \u00f6nerisini izleyin")
    name = (snapshot.target_name or "Sizin").strip()
    intro = f"{name} i\u00e7in sabah\u0131 yormayacak, pratik ve daha dengeli bir kahvalt\u0131 se\u00e7elim."
    note_text = f"\n\nK\u0131sa dikkat notu: {'; '.join(notes)}." if notes else ""
    return (
        f"{intro} Ben olsam bug\u00fcn \u015fu \u00fc\u00e7 se\u00e7enekten birini d\u00fc\u015f\u00fcn\u00fcrd\u00fcm:\n\n"
        "1. glutensiz yulaf kasesi: su veya \u015fekersiz bitkisel i\u00e7ecekle haz\u0131rlay\u0131n; \u00fczerine tar\u00e7\u0131n, chia ve az miktarda meyve ekleyin. Hafif, tok tutan ve kontroll\u00fc bir ba\u015flang\u0131\u00e7 olur.\n"
        "2. Avokadolu glutensiz tost: yan\u0131na salatal\u0131k, domates ve zeytin koyun. Daha tuzlu gelirse zeytini azaltmak iyi olur.\n"
        "3. Karabu\u011fday lapas\u0131: tar\u00e7\u0131nla tatland\u0131r\u0131p alerjen i\u00e7ermeyen tohumlarla tamamlay\u0131n. Mideyi daha sakin tutan, pratik bir alternatif.\n"
        f"{note_text}"
    )



def _safe_dinner_answer(snapshot: ResolvedProfileSnapshot) -> str:
    if snapshot.target_scope == "family":
        intro = "Hepiniz i\u00e7in ortak ve yormayan bir ak\u015fam yeme\u011fi se\u00e7elim. Ama\u00e7 tek tabakta hem kan \u015fekeri dengesini hem mide hassasiyetini hem de ya\u011f y\u00fck\u00fcn\u00fc sakin tutmak."
    else:
        name = (snapshot.target_name or "Sizin").strip()
        intro = f"{name} i\u00e7in bu ak\u015fam hafif, pratik ve profille \u00e7ak\u0131\u015fmayan bir tabak iyi gider."
    return (
        f"{intro} Ben olsam \u015fu se\u00e7eneklerden birini se\u00e7erdim:\n\n"
        "1. F\u0131r\u0131nda tavuk ve sebze: derisiz tavuk, kabak, havu\u00e7 ve az zeytinya\u011f\u0131yla haz\u0131rlan\u0131r. K\u0131zartma olmad\u0131\u011f\u0131 i\u00e7in daha hafif kal\u0131r.\n"
        "2. Izgara bal\u0131k ve sade salata: sosu ayr\u0131 isteyin; yo\u011fun limon, sirke ve ac\u0131 baharat kullanmay\u0131n. Kolesterol ve mide hassasiyeti i\u00e7in daha sakin bir se\u00e7im olur.\n"
        "3. Zeytinya\u011fl\u0131 taze fasulye yan\u0131nda yo\u011furtsuz/iste\u011fe g\u00f6re laktozsuz destek: porsiyon kontroll\u00fc, ev yeme\u011fi gibi g\u00fcvenli bir alternatif.\n\n"
        "D\u0131\u015far\u0131daysan\u0131z en pratik kural: k\u0131zartma, krema/sos ve \u00e7ok baharat yerine \u0131zgara veya f\u0131r\u0131n se\u00e7eneklerini sorun."
    )

def _diabetes_snack_answer() -> str:
    return (
        "Tatlı isteği için kan şekerini daha dengeli tutmaya yardımcı olabilecek pratik ara öğünler:\n"
        "- Tarçınlı yoğurt yerine süt alerjiniz varsa şekersiz bitkisel yoğurt alternatifi ve birkaç yaban mersini.\n"
        "- Bir küçük elma yanında alerjen içermeyen birkaç kabak çekirdeği.\n"
        "- Glutensiz, ilave şekersiz küçük chia pudingi.\n\n"
        "Porsiyonu küçük tutun; kan şekeri takibiniz veya ilaç planınız varsa kişisel sınırlar için uzman önerinizi izleyin."
    )


def _levothyroxine_timing_answer(snapshot: ResolvedProfileSnapshot, message: str) -> str:
    text = normalized_message(message)
    milk_note = ""
    if "badem" in text:
        milk_note = (
            "Badem sütü inek sütü proteiniyle aynı şey değildir; bu nedenle tek başına inek sütü alerjisi gibi değerlendirilmez. "
            "Yine de ürün etiketi ve çapraz bulaş bilgisini kontrol edin.\n\n"
        )
    timing_note = (
        "Levotiroksini kahvaltıyla aynı anda almak ilacın emilimini etkileyebilir. Aç veya tok kullanım ve kahvaltıyla "
        "bırakılacak süre kişisel tedavi planınıza göre değişebileceği için reçetenizdeki talimata ve doktorunuzun ya da "
        "eczacınızın önerisine uyun. Kalsiyum veya demir içeren ürün ve takviyeleri de ayrıca belirtin."
    )
    if not _profile_has(snapshot.medications, "levotiroksin", "levothyroxine"):
        return f"{milk_note}Profilinizde levotiroksin kaydı görünmüyor. Bu ilacı kullanıyorsanız profilinize ekleyip zamanlama kararını eczacınızla netleştirmeniz uygun olur."
    return f"{milk_note}{timing_note}"


def _warfarin_food_answer(snapshot: ResolvedProfileSnapshot) -> str:
    profile_note = ""
    if not _profile_has(snapshot.medications, "warfarin", "coumadin"):
        profile_note = "Profilinizde Warfarin kaydı görünmüyor; aşağıdaki bilgi genel niteliktedir.\n\n"
    return (
        f"{profile_note}Ispanak Warfarin kullanırken otomatik olarak tamamen yasak değildir. Önemli olan K vitamini "
        "içeren besinleri birden kesmek veya miktarını sık sık büyük ölçüde değiştirmek yerine tüketimi mümkün olduğunca "
        "düzenli tutmaktır. Size uygun miktarı ve sıklığı ilacınızı düzenleyen doktor veya eczacıyla netleştirin."
    )


def _ibs_tolerance_answer() -> str:
    return (
        "Nohutlu glutensiz salata herkes için otomatik olarak yasak değildir; ancak IBS'de nohut bazı kişilerde gaz veya "
        "şişkinliği artırabilir. Küçük porsiyonla denemek, soğan/sarımsak gibi tetikleyicileri azaltmak ve toleransınızı "
        "takip etmek daha uygun olur.\n\n"
        "Daha hafif alternatif olarak kinoa veya karabuğday tabanlı, soğansız ve sade soslu glutensiz bir salata deneyebilirsiniz."
    )


def _dessert_craving_answer(snapshot: ResolvedProfileSnapshot) -> str:
    allergy_note = " Kayıtlı alerjenlerini özellikle dışarıda bırakalım." if snapshot.allergies else ""
    return (
        "Canın tatlı çektiyse tamamen yasaklamak yerine küçük ve dengeli bir seçenek seçebiliriz.\n"
        "- Tarçınlı yoğurt veya laktozsuz yoğurtla küçük bir meyve porsiyonu\n"
        "- İlave şekeri düşük chia pudingi\n"
        "- Birkaç parça meyve ve yanında sade kahve\n\n"
        f"Porsiyonu küçük tutmak iyi olur.{allergy_note}"
    )


def _coffee_habit_answer(snapshot: ResolvedProfileSnapshot) -> str:
    return (
        "Kahveyi tamamen bırakman gerekmeyebilir; miktar, saat ve yanında ne tükettiğin daha belirleyici olabilir.\n"
        "- Gün içinde seni rahatsız etmeyen miktarı koru ve geç saatlere bırakmamaya çalış.\n"
        "- Şekerli şuruplar yerine sade kahve veya daha az şekerli bir seçenek deneyebilirsin.\n"
        "- Yanında küçük, dengeli bir atıştırmalık tercih etmek daha iyi olabilir.\n\n"
        "Çarpıntı, mide yakınması veya uyku sorunu yapıyorsa miktarı azaltıp kişisel toleransını takip et."
    )


def _explanation_followup_answer(snapshot: ResolvedProfileSnapshot) -> str:
    bullets = _profile_bullets(snapshot)
    details = "\n".join(f"- {item}" for item in bullets[:3])
    if not details:
        details = "- Alerji, hastalık, ilaç ve günlük hedefler\n- Porsiyon ve içerik dengesi\n- İsteğinin pratiklik ve damak tadına uygunluğu"
    return "Bu öneriyi şu ölçütleri birlikte düşünerek hazırladım:\n" + details + "\n\nİçeriği veya hedefi değiştirirsek öneriyi yeniden uyarlayabilirim."


def intent_fast_answer(snapshot: ResolvedProfileSnapshot, message: str) -> str | None:
    text = normalized_message(message)
    if any(phrase in text for phrase in ("bu oneriyi hangi kriter", "neden bu oneriyi", "neye gore verdin", "hangi kriterlere")):
        return _explanation_followup_answer(snapshot)
    if any(phrase in text for phrase in ("cani tatli cekti", "tatli canim", "tatli ne yesem", "tatli istiyorum")):
        return _dessert_craving_answer(snapshot)
    if any(phrase in text for phrase in ("kahveyi cok seviyorum", "kahve iciyorum", "kahvem", "kahve saglig")):
        return _coffee_habit_answer(snapshot)
    if any(phrase in text for phrase in ("arkanda ne var", "nasil yapiyorsun", "sana guven", "guvenebilir miyim", "neye gore calis")):
        return _product_trust_answer()
    if any(phrase in text for phrase in ("curemenu nedir", "nasil kis", "nasil calis", "yemek kararlarimi nasil", "verilerimi nasil", "verilerimi neden")):
        return _product_info_answer()
    if any(phrase in text for phrase in ("neden verdin", "hangi saglik bilgilerimi", "neyi dikkate aldin", "neden oner")):
        bullets = _profile_bullets(snapshot)
        if not bullets:
            return "Bu öneride kayıtlı profil bilgilerinizden belirgin bir sağlık kısıtı görünmüyor. Yine de tercih, hedef ve önceki kullanım bilgileriniz önerinin kişiselleştirilmesinde kullanılabilir."
        return "Önceki öneriyi, seçtiğiniz profilin ihtiyaçlarıyla çakışmayacak bir seçenek sunmak için verdim. Özellikle şunları dikkate aldım:\n" + "\n".join(f"- {item}" for item in bullets)
    if "levotiroksin" in text or "levothyroxine" in text:
        return _levothyroxine_timing_answer(snapshot, message)
    if "warfarin" in text or "coumadin" in text:
        return _warfarin_food_answer(snapshot)
    if "ibs" in text or "irritabl" in text:
        return _ibs_tolerance_answer()
    safe_request = bool(re.search(r"\boner(?:i|ir|irsin|ir misin|ebilir misin)?\b", text)) or any(
        term in text for term in ("alternatif", "ara ogun")
    )
    breakfast_request = safe_request and any(
        term in text for term in ("kahvalti", "sabah", "pratik kahvalti", "kisa kahvalti")
    )
    dinner_request = safe_request and any(
        term in text for term in ("aksam yemegi", "ak?am yeme?i", "aksam", "ak?am", "yemek", "ogun", "???n")
    )
    safe_request = safe_request and any(
        term in text for term in ("yumurtasiz", "sutsuz", "glutensiz", "diyabete uygun", "tatli iste")
    )
    if safe_request and "tatli" in text:
        return _diabetes_snack_answer()
    if breakfast_request:
        return _safe_breakfast_answer(snapshot)
    if dinner_request:
        return _safe_dinner_answer(snapshot)
    if safe_request:
        return _safe_breakfast_answer(snapshot)
    return None


def merge_medications(profile_medications: list[str], message: str) -> tuple[list[str], list[str]]:
    message_medications = extract_medication_mentions(message)
    merged: list[str] = []
    seen: set[str] = set()
    for medication in [*(profile_medications or []), *message_medications]:
        key = normalize_text(str(medication))
        if key and key not in seen:
            seen.add(key)
            merged.append(str(medication).strip())
    return merged, message_medications
