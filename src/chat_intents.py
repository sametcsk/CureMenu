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
    if _profile_has(snapshot.diseases, "çölyak", "celiac", "gluten"):
        notes.append("glutensiz sertifikalı ürün kullanın")
    if _profile_has(snapshot.diseases, "diyabet", "diabetes"):
        notes.append("meyve ve tahıl porsiyonunu ölçülü tutun")
    if _profile_has(snapshot.diseases, "böbrek", "renal", "ckd"):
        notes.append("böbrek durumunuz varsa protein ve porsiyon sınırını sağlık profesyonelinizle netleştirin")
    if _profile_has(snapshot.medications, "levotiroksin", "levothyroxine"):
        notes.append("levotiroksin zamanlaması için doktor/eczacı önerinizi izleyin")
    note_text = f"\n\nKısa not: {', '.join(notes)}." if notes else ""
    return (
        "Evet, kayıtlı alerjenleri dışarıda bırakan bir kahvaltı alternatifi hazırlanabilir. "
        "Örnekler:\n"
        "- Su veya şekersiz bitki bazlı içecekle hazırlanmış glutensiz yulaf; üzerine tarçın, chia ve küçük porsiyon meyve.\n"
        "- Avokadolu glutensiz tost; yanında salatalık, domates ve zeytin.\n"
        "- Karabuğday lapası; üzerine tahin yerine alerjen içermeyen tohum karışımı ve tarçın.\n"
        f"{note_text}"
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


def intent_fast_answer(snapshot: ResolvedProfileSnapshot, message: str) -> str | None:
    text = normalized_message(message)
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
    safe_request = safe_request and any(
        term in text for term in ("yumurtasiz", "sutsuz", "glutensiz", "diyabete uygun", "tatli iste")
    )
    if safe_request and "tatli" in text:
        return _diabetes_snack_answer()
    if safe_request or breakfast_request:
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
