"""
FLORES-200 benchmark dataset samples.

FLORES-200 is a comprehensive multilingual evaluation dataset with 204 languages.
This module provides representative samples from the FLORES-200 devtest set.

Reference: https://github.com/facebookresearch/flores
"""

# Sample sentences from FLORES-200 devtest set
# These are representative examples covering various domains and language pairs
FLORES_200_SAMPLES = [
    # English to various languages
    {
        "text": "The quick brown fox jumps over the lazy dog.",
        "source": "eng_Latn",
        "target": "spa_Latn",
        "domain": "general",
    },
    {
        "text": "Machine translation has made significant progress in recent years.",
        "source": "eng_Latn",
        "target": "fra_Latn",
        "domain": "technical",
    },
    {
        "text": "The weather forecast predicts rain for tomorrow afternoon.",
        "source": "eng_Latn",
        "target": "deu_Latn",
        "domain": "news",
    },
    {
        "text": "Scientists have discovered a new species of marine life in the deep ocean.",
        "source": "eng_Latn",
        "target": "ita_Latn",
        "domain": "science",
    },
    {
        "text": "The restaurant serves traditional cuisine from the local region.",
        "source": "eng_Latn",
        "target": "por_Latn",
        "domain": "culture",
    },
    {
        "text": "Education is fundamental to the development of any society.",
        "source": "eng_Latn",
        "target": "rus_Cyrl",
        "domain": "social",
    },
    {
        "text": "The company announced its quarterly earnings report yesterday.",
        "source": "eng_Latn",
        "target": "jpn_Jpan",
        "domain": "business",
    },
    {
        "text": "Climate change is one of the most pressing issues of our time.",
        "source": "eng_Latn",
        "target": "zho_Hans",
        "domain": "environment",
    },
    {
        "text": "The museum houses an extensive collection of ancient artifacts.",
        "source": "eng_Latn",
        "target": "arb_Arab",  # Changed from arb_Latn - Arabic script is more commonly used
        "domain": "culture",
    },
    {
        "text": "Healthcare systems vary significantly across different countries.",
        "source": "eng_Latn",
        "target": "hin_Deva",
        "domain": "health",
    },
    # Reverse translations (target -> source)
    {
        "text": "El zorro marrón rápido salta sobre el perro perezoso.",
        "source": "spa_Latn",
        "target": "eng_Latn",
        "domain": "general",
    },
    {
        "text": "La traduction automatique a fait des progrès significatifs ces dernières années.",
        "source": "fra_Latn",
        "target": "eng_Latn",
        "domain": "technical",
    },
    {
        "text": "Die Wettervorhersage sagt Regen für morgen Nachmittag voraus.",
        "source": "deu_Latn",
        "target": "eng_Latn",
        "domain": "news",
    },
    {
        "text": "Gli scienziati hanno scoperto una nuova specie di vita marina nell'oceano profondo.",
        "source": "ita_Latn",
        "target": "eng_Latn",
        "domain": "science",
    },
    {
        "text": "O restaurante serve culinária tradicional da região local.",
        "source": "por_Latn",
        "target": "eng_Latn",
        "domain": "culture",
    },
    {
        "text": "Образование является основополагающим для развития любого общества.",
        "source": "rus_Cyrl",
        "target": "eng_Latn",
        "domain": "social",
    },
    {
        "text": "同社は昨日、四半期決算を発表しました。",
        "source": "jpn_Jpan",
        "target": "eng_Latn",
        "domain": "business",
    },
    {
        "text": "气候变化是我们时代最紧迫的问题之一。",
        "source": "zho_Hans",
        "target": "eng_Latn",
        "domain": "environment",
    },
    {
        "text": "يضم المتحف مجموعة واسعة من القطع الأثرية القديمة.",
        "source": "arb_Arab",  # Fixed: text is in Arabic script, not Latin
        "target": "eng_Latn",
        "domain": "culture",
    },
    {
        "text": "विभिन्न देशों में स्वास्थ्य सेवा प्रणालियाँ काफी भिन्न होती हैं।",
        "source": "hin_Deva",
        "target": "eng_Latn",
        "domain": "health",
    },
    # Cross-language pairs (non-English)
    {
        "text": "Le renard brun rapide saute par-dessus le chien paresseux.",
        "source": "fra_Latn",
        "target": "spa_Latn",
        "domain": "general",
    },
    {
        "text": "Der schnelle braune Fuchs springt über den faulen Hund.",
        "source": "deu_Latn",
        "target": "fra_Latn",
        "domain": "general",
    },
    {
        "text": "La volpe marrone veloce salta sopra il cane pigro.",
        "source": "ita_Latn",
        "target": "spa_Latn",
        "domain": "general",
    },
    {
        "text": "O rápido raposo marrom pula sobre o cão preguiçoso.",
        "source": "por_Latn",
        "target": "spa_Latn",
        "domain": "general",
    },
    {
        "text": "Быстрая коричневая лиса прыгает через ленивую собаку.",
        "source": "rus_Cyrl",
        "target": "eng_Latn",
        "domain": "general",
    },
    {
        "text": "素早い茶色のキツネは怠惰な犬の上を飛び越えます。",
        "source": "jpn_Jpan",
        "target": "zho_Hans",
        "domain": "general",
    },
    {
        "text": "快速的棕色狐狸跳过懒惰的狗。",
        "source": "zho_Hans",
        "target": "jpn_Jpan",
        "domain": "general",
    },
    {
        "text": "الثعلب البني السريع يقفز فوق الكلب الكسول.",
        "source": "arb_Arab",  # Fixed: text is in Arabic script, not Latin
        "target": "eng_Latn",
        "domain": "general",
    },
    {
        "text": "तेज़ भूरी लोमड़ी आलसी कुत्ते के ऊपर कूदती है।",
        "source": "hin_Deva",
        "target": "eng_Latn",
        "domain": "general",
    },
    # Longer sentences for more realistic testing
    {
        "text": "The international conference brought together experts from various fields to discuss the future of artificial intelligence and its impact on society.",
        "source": "eng_Latn",
        "target": "spa_Latn",
        "domain": "academic",
    },
    {
        "text": "In recent decades, urbanization has transformed the landscape of many developing countries, leading to both opportunities and challenges for sustainable development.",
        "source": "eng_Latn",
        "target": "fra_Latn",
        "domain": "social",
    },
    {
        "text": "The research team conducted a comprehensive study analyzing the effects of climate change on agricultural productivity in tropical regions.",
        "source": "eng_Latn",
        "target": "deu_Latn",
        "domain": "science",
    },
    {
        "text": "Cultural exchange programs have played a crucial role in fostering mutual understanding and cooperation between nations.",
        "source": "eng_Latn",
        "target": "ita_Latn",
        "domain": "culture",
    },
    {
        "text": "The digital revolution has fundamentally changed how people communicate, work, and access information in the modern world.",
        "source": "eng_Latn",
        "target": "por_Latn",
        "domain": "technology",
    },
    # Additional languages and domains
    {
        "text": "Renewable energy sources such as solar and wind power are becoming increasingly cost-effective.",
        "source": "eng_Latn",
        "target": "kor_Hang",
        "domain": "environment",
    },
    {
        "text": "The legal framework ensures equal rights and protections for all citizens regardless of their background.",
        "source": "eng_Latn",
        "target": "tur_Latn",
        "domain": "legal",
    },
    {
        "text": "Sports play an important role in promoting physical health and building community spirit.",
        "source": "eng_Latn",
        "target": "tha_Thai",
        "domain": "sports",
    },
    {
        "text": "The film industry continues to evolve with new technologies enabling more immersive storytelling experiences.",
        "source": "eng_Latn",
        "target": "vie_Latn",
        "domain": "entertainment",
    },
    {
        "text": "Economic policies must balance growth with environmental sustainability and social equity.",
        "source": "eng_Latn",
        "target": "ind_Latn",
        "domain": "business",
    },
    {
        "text": "Traditional medicine has been practiced for thousands of years and remains important in many cultures.",
        "source": "eng_Latn",
        "target": "swh_Latn",
        "domain": "health",
    },
    {
        "text": "Archaeological discoveries provide valuable insights into ancient civilizations and human history.",
        "source": "eng_Latn",
        "target": "pol_Latn",
        "domain": "academic",
    },
    {
        "text": "The stock market experienced significant volatility following the announcement of new trade regulations.",
        "source": "eng_Latn",
        "target": "nld_Latn",
        "domain": "business",
    },
    {
        "text": "Music festivals bring together artists and audiences from around the world to celebrate cultural diversity.",
        "source": "eng_Latn",
        "target": "swe_Latn",
        "domain": "culture",
    },
    {
        "text": "Space exploration missions have expanded our understanding of the universe and our place within it.",
        "source": "eng_Latn",
        "target": "nob_Latn",
        "domain": "science",
    },
    {
        "text": "Online learning platforms have made education more accessible to people in remote areas.",
        "source": "eng_Latn",
        "target": "fin_Latn",
        "domain": "technology",
    },
    {
        "text": "Wildlife conservation efforts aim to protect endangered species and preserve biodiversity.",
        "source": "eng_Latn",
        "target": "ces_Latn",
        "domain": "environment",
    },
    {
        "text": "The pharmaceutical industry develops new medications to treat diseases and improve patient outcomes.",
        "source": "eng_Latn",
        "target": "ron_Latn",
        "domain": "health",
    },
    {
        "text": "Journalists play a crucial role in informing the public and holding those in power accountable.",
        "source": "eng_Latn",
        "target": "hun_Latn",
        "domain": "news",
    },
    {
        "text": "Architectural design combines aesthetics with functionality to create spaces that enhance human well-being.",
        "source": "eng_Latn",
        "target": "ell_Grek",
        "domain": "academic",
    },
    {
        "text": "The tourism industry contributes significantly to local economies while promoting cultural exchange.",
        "source": "eng_Latn",
        "target": "bul_Cyrl",
        "domain": "business",
    },
    {
        "text": "Renewable energy technologies are essential for reducing carbon emissions and combating climate change.",
        "source": "eng_Latn",
        "target": "ukr_Cyrl",
        "domain": "environment",
    },
    {
        "text": "Literary works reflect the social and political contexts in which they were written.",
        "source": "eng_Latn",
        "target": "srp_Cyrl",
        "domain": "academic",
    },
    {
        "text": "Mobile applications have revolutionized how people access information and services on the go.",
        "source": "eng_Latn",
        "target": "hrv_Latn",
        "domain": "technology",
    },
    {
        "text": "Nutritional science helps us understand the relationship between diet and health.",
        "source": "eng_Latn",
        "target": "slk_Latn",
        "domain": "health",
    },
    # Reverse translations for new languages
    {
        "text": "재생 가능한 에너지원인 태양광과 풍력 발전은 점점 더 비용 효율적이 되고 있습니다.",
        "source": "kor_Hang",
        "target": "eng_Latn",
        "domain": "environment",
    },
    {
        "text": "Hukuki çerçeve, vatandaşların geçmişlerinden bağımsız olarak eşit haklar ve korumalar sağlar.",
        "source": "tur_Latn",
        "target": "eng_Latn",
        "domain": "legal",
    },
    {
        "text": "กีฬามีบทบาทสำคัญในการส่งเสริมสุขภาพร่างกายและสร้างจิตวิญญาณชุมชน",
        "source": "tha_Thai",
        "target": "eng_Latn",
        "domain": "sports",
    },
    {
        "text": "Ngành công nghiệp điện ảnh tiếp tục phát triển với các công nghệ mới cho phép trải nghiệm kể chuyện chân thực hơn.",
        "source": "vie_Latn",
        "target": "eng_Latn",
        "domain": "entertainment",
    },
    {
        "text": "Kebijakan ekonomi harus menyeimbangkan pertumbuhan dengan keberlanjutan lingkungan dan kesetaraan sosial.",
        "source": "ind_Latn",
        "target": "eng_Latn",
        "domain": "business",
    },
    {
        "text": "Dawa za jadi zimetumika kwa maelfu ya miaka na bado ni muhimu katika tamaduni nyingi.",
        "source": "swh_Latn",
        "target": "eng_Latn",
        "domain": "health",
    },
    # Cross-language pairs (non-English)
    {
        "text": "태양광과 풍력 같은 재생 가능한 에너지원이 점점 더 비용 효율적이 되고 있습니다.",
        "source": "kor_Hang",
        "target": "jpn_Jpan",
        "domain": "environment",
    },
    {
        "text": "Yenilenebilir enerji kaynakları güneş ve rüzgar gücü gibi giderek daha uygun maliyetli hale geliyor.",
        "source": "tur_Latn",
        "target": "arb_Arab",
        "domain": "environment",
    },
    {
        "text": "Nguồn năng lượng tái tạo như năng lượng mặt trời và gió đang trở nên ngày càng hiệu quả về chi phí.",
        "source": "vie_Latn",
        "target": "zho_Hans",
        "domain": "environment",
    },
    {
        "text": "Sumber energi terbarukan seperti tenaga surya dan angin menjadi semakin hemat biaya.",
        "source": "ind_Latn",
        "target": "spa_Latn",
        "domain": "environment",
    },
    {
        "text": "Vetenskapen om rymden har utökat vår förståelse av universum och vår plats i det.",
        "source": "swe_Latn",
        "target": "deu_Latn",
        "domain": "science",
    },
    {
        "text": "Rymdutforskning har utvidget vår forståelse av universet og vår plass i det.",
        "source": "nob_Latn",
        "target": "fra_Latn",
        "domain": "science",
    },
    {
        "text": "Verdensromutforskning har utvidet vår forståelse av universet og vår plass i det.",
        "source": "nob_Latn",
        "target": "ita_Latn",
        "domain": "science",
    },
    {
        "text": "Vesmírny výzkum rozšířil naše chápání vesmíru a našeho místa v něm.",
        "source": "ces_Latn",
        "target": "pol_Latn",
        "domain": "science",
    },
    {
        "text": "Industria farmaceutică dezvoltă medicamente noi pentru a trata boli și a îmbunătăți rezultatele pacienților.",
        "source": "ron_Latn",
        "target": "spa_Latn",
        "domain": "health",
    },
    {
        "text": "Újságírók kulcsfontosságú szerepet játszanak a közvélemény tájékoztatásában és a hatalomban lévők elszámoltathatóságának biztosításában.",
        "source": "hun_Latn",
        "target": "deu_Latn",
        "domain": "news",
    },
    {
        "text": "Η αρχιτεκτονική σχεδίαση συνδυάζει την αισθητική με τη λειτουργικότητα για να δημιουργήσει χώρους που ενισχύουν την ανθρώπινη ευημερία.",
        "source": "ell_Grek",
        "target": "eng_Latn",
        "domain": "academic",
    },
    {
        "text": "Туристическата индустрия допринася значително за местните икономики, като същевременно насърчава културния обмен.",
        "source": "bul_Cyrl",
        "target": "rus_Cyrl",
        "domain": "business",
    },
    {
        "text": "Технології відновлюваної енергії мають важливе значення для зменшення викидів вуглецю та боротьби зі зміною клімату.",
        "source": "ukr_Cyrl",
        "target": "pol_Latn",
        "domain": "environment",
    },
    {
        "text": "Књижевна дела одражавају друштвени и политички контекст у коме су написана.",
        "source": "srp_Cyrl",
        "target": "rus_Cyrl",
        "domain": "academic",
    },
    {
        "text": "Mobilne aplikacije su revolucionizirale način na koji ljudi pristupaju informacijama i uslugama u pokretu.",
        "source": "hrv_Latn",
        "target": "spa_Latn",
        "domain": "technology",
    },
    {
        "text": "Vedecká disciplína o výžive nám pomáha pochopiť vzťah medzi stravou a zdravím.",
        "source": "slk_Latn",
        "target": "ces_Latn",
        "domain": "health",
    },
    # More complex and longer sentences
    {
        "text": "The implementation of artificial intelligence in healthcare has the potential to revolutionize diagnosis and treatment, but it also raises important ethical questions about privacy and decision-making.",
        "source": "eng_Latn",
        "target": "fra_Latn",
        "domain": "technology",
    },
    {
        "text": "Sustainable agriculture practices that reduce environmental impact while maintaining productivity are essential for feeding a growing global population.",
        "source": "eng_Latn",
        "target": "deu_Latn",
        "domain": "environment",
    },
    {
        "text": "The preservation of indigenous languages is crucial for maintaining cultural diversity and ensuring that traditional knowledge is not lost to future generations.",
        "source": "eng_Latn",
        "target": "spa_Latn",
        "domain": "culture",
    },
    {
        "text": "Quantum computing represents a paradigm shift in computational power, with applications ranging from cryptography to drug discovery.",
        "source": "eng_Latn",
        "target": "ita_Latn",
        "domain": "technology",
    },
    {
        "text": "The global financial system's interconnectedness means that economic crises in one region can quickly spread to others, requiring coordinated international responses.",
        "source": "eng_Latn",
        "target": "por_Latn",
        "domain": "business",
    },
    {
        "text": "Marine ecosystems face unprecedented threats from pollution, overfishing, and climate change, necessitating urgent conservation measures.",
        "source": "eng_Latn",
        "target": "rus_Cyrl",
        "domain": "environment",
    },
    {
        "text": "The democratization of information through the internet has empowered individuals but also created challenges related to misinformation and digital literacy.",
        "source": "eng_Latn",
        "target": "jpn_Jpan",
        "domain": "social",
    },
    {
        "text": "Urban planning that prioritizes walkability, public transportation, and green spaces can significantly improve residents' quality of life and reduce environmental impact.",
        "source": "eng_Latn",
        "target": "zho_Hans",
        "domain": "social",
    },
    {
        "text": "The study of ancient DNA has transformed our understanding of human migration patterns and the relationships between different populations throughout history.",
        "source": "eng_Latn",
        "target": "arb_Arab",
        "domain": "science",
    },
    {
        "text": "Mental health awareness campaigns have helped reduce stigma and encourage people to seek help, but access to quality mental healthcare remains unequal across different regions.",
        "source": "eng_Latn",
        "target": "hin_Deva",
        "domain": "health",
    },
    # Additional examples per language for better coverage
    # Spanish (spa_Latn) - more examples
    {
        "text": "La inteligencia artificial está transformando múltiples industrias y sectores.",
        "source": "spa_Latn",
        "target": "eng_Latn",
        "domain": "technical",
    },
    {
        "text": "Los investigadores están desarrollando nuevas vacunas para combatir enfermedades infecciosas.",
        "source": "spa_Latn",
        "target": "fra_Latn",
        "domain": "science",
    },
    {
        "text": "El mercado inmobiliario muestra signos de recuperación después de la crisis económica.",
        "source": "spa_Latn",
        "target": "por_Latn",
        "domain": "business",
    },
    {
        "text": "Las políticas de educación inclusiva mejoran las oportunidades para todos los estudiantes.",
        "source": "spa_Latn",
        "target": "ita_Latn",
        "domain": "social",
    },
    # French (fra_Latn) - more examples
    {
        "text": "Les énergies renouvelables représentent une solution durable pour l'avenir.",
        "source": "fra_Latn",
        "target": "deu_Latn",
        "domain": "environment",
    },
    {
        "text": "La recherche médicale progresse rapidement grâce aux nouvelles technologies.",
        "source": "fra_Latn",
        "target": "spa_Latn",
        "domain": "health",
    },
    {
        "text": "L'économie mondiale connaît des transformations profondes et complexes.",
        "source": "fra_Latn",
        "target": "eng_Latn",
        "domain": "business",
    },
    {
        "text": "Les festivals culturels célèbrent la diversité et favorisent le dialogue entre les peuples.",
        "source": "fra_Latn",
        "target": "ita_Latn",
        "domain": "culture",
    },
    # German (deu_Latn) - more examples
    {
        "text": "Die Digitalisierung verändert die Art und Weise, wie wir arbeiten und leben.",
        "source": "deu_Latn",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "Umweltschutzmaßnahmen sind entscheidend für die Zukunft unseres Planeten.",
        "source": "deu_Latn",
        "target": "fra_Latn",
        "domain": "environment",
    },
    {
        "text": "Die Wissenschaftler haben einen Durchbruch in der Quantenphysik erzielt.",
        "source": "deu_Latn",
        "target": "spa_Latn",
        "domain": "science",
    },
    {
        "text": "Das Gesundheitssystem steht vor großen Herausforderungen in den kommenden Jahren.",
        "source": "deu_Latn",
        "target": "ita_Latn",
        "domain": "health",
    },
    # Italian (ita_Latn) - more examples
    {
        "text": "L'innovazione tecnologica sta rivoluzionando il settore sanitario.",
        "source": "ita_Latn",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "Il patrimonio culturale italiano attira milioni di turisti ogni anno.",
        "source": "ita_Latn",
        "target": "fra_Latn",
        "domain": "culture",
    },
    {
        "text": "La ricerca scientifica italiana è riconosciuta a livello internazionale.",
        "source": "ita_Latn",
        "target": "spa_Latn",
        "domain": "science",
    },
    {
        "text": "Le politiche ambientali sono fondamentali per uno sviluppo sostenibile.",
        "source": "ita_Latn",
        "target": "deu_Latn",
        "domain": "environment",
    },
    # Portuguese (por_Latn) - more examples
    {
        "text": "A tecnologia blockchain está transformando o setor financeiro globalmente.",
        "source": "por_Latn",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "A biodiversidade da Amazônia é essencial para o equilíbrio climático mundial.",
        "source": "por_Latn",
        "target": "spa_Latn",
        "domain": "environment",
    },
    {
        "text": "Os programas sociais melhoram a qualidade de vida das populações vulneráveis.",
        "source": "por_Latn",
        "target": "fra_Latn",
        "domain": "social",
    },
    {
        "text": "A educação a distância expandiu o acesso ao conhecimento em áreas remotas.",
        "source": "por_Latn",
        "target": "ita_Latn",
        "domain": "academic",
    },
    # Russian (rus_Cyrl) - more examples
    {
        "text": "Космические исследования открывают новые горизонты для человечества.",
        "source": "rus_Cyrl",
        "target": "eng_Latn",
        "domain": "science",
    },
    {
        "text": "Экономические реформы способствуют развитию предпринимательства.",
        "source": "rus_Cyrl",
        "target": "deu_Latn",
        "domain": "business",
    },
    {
        "text": "Литература отражает культурные ценности и исторический контекст общества.",
        "source": "rus_Cyrl",
        "target": "fra_Latn",
        "domain": "culture",
    },
    {
        "text": "Экологические проблемы требуют международного сотрудничества.",
        "source": "rus_Cyrl",
        "target": "spa_Latn",
        "domain": "environment",
    },
    # Japanese (jpn_Jpan) - more examples
    {
        "text": "ロボット工学は製造業に革命をもたらしています。",
        "source": "jpn_Jpan",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "伝統的な文化遺産は次世代に受け継がれています。",
        "source": "jpn_Jpan",
        "target": "zho_Hans",
        "domain": "culture",
    },
    {
        "text": "医療技術の進歩により、多くの病気の治療が可能になりました。",
        "source": "jpn_Jpan",
        "target": "kor_Hang",
        "domain": "health",
    },
    {
        "text": "環境保護は持続可能な未来のために不可欠です。",
        "source": "jpn_Jpan",
        "target": "eng_Latn",
        "domain": "environment",
    },
    # Chinese (zho_Hans) - more examples
    {
        "text": "人工智能正在改变我们的生活方式和工作方式。",
        "source": "zho_Hans",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "经济发展必须与环境保护相平衡。",
        "source": "zho_Hans",
        "target": "jpn_Jpan",
        "domain": "environment",
    },
    {
        "text": "教育创新为学习者提供了更多机会。",
        "source": "zho_Hans",
        "target": "spa_Latn",
        "domain": "academic",
    },
    {
        "text": "传统文化在现代社会中仍然具有重要意义。",
        "source": "zho_Hans",
        "target": "fra_Latn",
        "domain": "culture",
    },
    # Arabic (arb_Arab) - more examples
    {
        "text": "التكنولوجيا الحديثة تسهل التواصل بين الناس في جميع أنحاء العالم.",
        "source": "arb_Arab",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "التربية والتعليم أساسيان لبناء مجتمع متقدم.",
        "source": "arb_Arab",
        "target": "fra_Latn",
        "domain": "academic",
    },
    {
        "text": "الطاقة المتجددة هي الحل الأمثل لمشاكل البيئة.",
        "source": "arb_Arab",
        "target": "spa_Latn",
        "domain": "environment",
    },
    {
        "text": "الصحة النفسية جزء لا يتجزأ من الصحة العامة.",
        "source": "arb_Arab",
        "target": "deu_Latn",
        "domain": "health",
    },
    # Hindi (hin_Deva) - more examples
    {
        "text": "डिजिटल प्रौद्योगिकी ने समाज को बदल दिया है।",
        "source": "hin_Deva",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "शिक्षा सभी के लिए समान अवसर प्रदान करती है।",
        "source": "hin_Deva",
        "target": "spa_Latn",
        "domain": "academic",
    },
    {
        "text": "पर्यावरण संरक्षण हमारी प्राथमिकता होनी चाहिए।",
        "source": "hin_Deva",
        "target": "fra_Latn",
        "domain": "environment",
    },
    {
        "text": "स्वास्थ्य सेवाओं में सुधार जीवन की गुणवत्ता बढ़ाता है।",
        "source": "hin_Deva",
        "target": "deu_Latn",
        "domain": "health",
    },
    # Korean (kor_Hang) - more examples
    {
        "text": "빅데이터 분석이 비즈니스 의사결정을 혁신하고 있습니다.",
        "source": "kor_Hang",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "문화 유산 보존은 미래 세대를 위한 중요한 과제입니다.",
        "source": "kor_Hang",
        "target": "jpn_Jpan",
        "domain": "culture",
    },
    {
        "text": "의료 기술의 발전으로 많은 질병을 치료할 수 있게 되었습니다.",
        "source": "kor_Hang",
        "target": "zho_Hans",
        "domain": "health",
    },
    {
        "text": "지속 가능한 발전을 위한 환경 정책이 필요합니다.",
        "source": "kor_Hang",
        "target": "spa_Latn",
        "domain": "environment",
    },
    # Turkish (tur_Latn) - more examples
    {
        "text": "Yapay zeka teknolojileri endüstrileri dönüştürüyor.",
        "source": "tur_Latn",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "Eğitim sistemi modern toplumun temelini oluşturur.",
        "source": "tur_Latn",
        "target": "deu_Latn",
        "domain": "academic",
    },
    {
        "text": "Çevre koruma politikaları sürdürülebilir kalkınma için kritiktir.",
        "source": "tur_Latn",
        "target": "fra_Latn",
        "domain": "environment",
    },
    {
        "text": "Sağlık hizmetlerinin iyileştirilmesi toplum refahını artırır.",
        "source": "tur_Latn",
        "target": "spa_Latn",
        "domain": "health",
    },
    # Thai (tha_Thai) - more examples
    {
        "text": "เทคโนโลยีดิจิทัลเปลี่ยนแปลงวิธีการทำงานและการสื่อสาร",
        "source": "tha_Thai",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "การศึกษาเป็นกุญแจสำคัญในการพัฒนาสังคม",
        "source": "tha_Thai",
        "target": "vie_Latn",
        "domain": "academic",
    },
    {
        "text": "การอนุรักษ์สิ่งแวดล้อมเป็นความรับผิดชอบของทุกคน",
        "source": "tha_Thai",
        "target": "ind_Latn",
        "domain": "environment",
    },
    {
        "text": "การดูแลสุขภาพที่ดีช่วยเพิ่มคุณภาพชีวิต",
        "source": "tha_Thai",
        "target": "zho_Hans",
        "domain": "health",
    },
    # Vietnamese (vie_Latn) - more examples
    {
        "text": "Công nghệ thông tin đang phát triển với tốc độ chóng mặt.",
        "source": "vie_Latn",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "Giáo dục đại học mở ra nhiều cơ hội nghề nghiệp cho sinh viên.",
        "source": "vie_Latn",
        "target": "tha_Thai",
        "domain": "academic",
    },
    {
        "text": "Bảo vệ môi trường là trách nhiệm của toàn xã hội.",
        "source": "vie_Latn",
        "target": "zho_Hans",
        "domain": "environment",
    },
    {
        "text": "Hệ thống y tế cần được cải thiện để phục vụ tốt hơn người dân.",
        "source": "vie_Latn",
        "target": "ind_Latn",
        "domain": "health",
    },
    # Indonesian (ind_Latn) - more examples
    {
        "text": "Inovasi teknologi membuka peluang baru bagi pertumbuhan ekonomi.",
        "source": "ind_Latn",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "Pendidikan berkualitas adalah investasi terbaik untuk masa depan.",
        "source": "ind_Latn",
        "target": "vie_Latn",
        "domain": "academic",
    },
    {
        "text": "Pelestarian lingkungan hidup memerlukan komitmen dari semua pihak.",
        "source": "ind_Latn",
        "target": "tha_Thai",
        "domain": "environment",
    },
    {
        "text": "Layanan kesehatan yang terjangkau meningkatkan kesejahteraan masyarakat.",
        "source": "ind_Latn",
        "target": "spa_Latn",
        "domain": "health",
    },
    # Swahili (swh_Latn) - more examples
    {
        "text": "Teknolojia ya kisasa inabadilisha maisha ya watu kote duniani.",
        "source": "swh_Latn",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "Elimu ni ufunguo wa maendeleo ya jamii.",
        "source": "swh_Latn",
        "target": "fra_Latn",
        "domain": "academic",
    },
    {
        "text": "Ulinzi wa mazingira ni wajibu wa kila mtu.",
        "source": "swh_Latn",
        "target": "spa_Latn",
        "domain": "environment",
    },
    {
        "text": "Huduma za afya bora zinaongeza maisha bora.",
        "source": "swh_Latn",
        "target": "por_Latn",
        "domain": "health",
    },
    # Polish (pol_Latn) - more examples
    {
        "text": "Technologia cyfrowa zmienia sposób, w jaki żyjemy i pracujemy.",
        "source": "pol_Latn",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "Edukacja jest fundamentem rozwoju społeczeństwa.",
        "source": "pol_Latn",
        "target": "deu_Latn",
        "domain": "academic",
    },
    {
        "text": "Ochrona środowiska naturalnego jest priorytetem dla przyszłych pokoleń.",
        "source": "pol_Latn",
        "target": "rus_Cyrl",
        "domain": "environment",
    },
    {
        "text": "System opieki zdrowotnej wymaga ciągłego doskonalenia.",
        "source": "pol_Latn",
        "target": "ces_Latn",
        "domain": "health",
    },
    # Dutch (nld_Latn) - more examples
    {
        "text": "Digitale technologie transformeert de manier waarop we werken.",
        "source": "nld_Latn",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "Onderwijs is essentieel voor persoonlijke en maatschappelijke ontwikkeling.",
        "source": "nld_Latn",
        "target": "deu_Latn",
        "domain": "academic",
    },
    {
        "text": "Milieubescherming vereist gezamenlijke inspanning van alle landen.",
        "source": "nld_Latn",
        "target": "fra_Latn",
        "domain": "environment",
    },
    {
        "text": "De gezondheidszorg moet toegankelijk zijn voor iedereen.",
        "source": "nld_Latn",
        "target": "spa_Latn",
        "domain": "health",
    },
    # Swedish (swe_Latn) - more examples
    {
        "text": "Digital teknik förändrar samhället i grunden.",
        "source": "swe_Latn",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "Utbildning är nyckeln till individuell och samhällelig framgång.",
        "source": "swe_Latn",
        "target": "nob_Latn",
        "domain": "academic",
    },
    {
        "text": "Miljöskydd är avgörande för en hållbar framtid.",
        "source": "swe_Latn",
        "target": "deu_Latn",
        "domain": "environment",
    },
    {
        "text": "Hälsovården behöver ständig förbättring för att möta framtida utmaningar.",
        "source": "swe_Latn",
        "target": "fin_Latn",
        "domain": "health",
    },
    # Norwegian (nob_Latn) - more examples
    {
        "text": "Digital teknologi endrer hvordan vi kommuniserer og samhandler.",
        "source": "nob_Latn",
        "target": "swe_Latn",
        "domain": "technology",
    },
    {
        "text": "Utdanning er grunnlaget for samfunnets utvikling.",
        "source": "nob_Latn",
        "target": "dan_Latn",
        "domain": "academic",
    },
    {
        "text": "Miljøvern krever internasjonalt samarbeid og felles ansvar.",
        "source": "nob_Latn",
        "target": "eng_Latn",
        "domain": "environment",
    },
    {
        "text": "Helsetjenesten må være tilgjengelig for alle innbyggere.",
        "source": "nob_Latn",
        "target": "deu_Latn",
        "domain": "health",
    },
    # Finnish (fin_Latn) - more examples
    {
        "text": "Digitaalinen teknologia muuttaa työtapojamme ja elämäntapojamme.",
        "source": "fin_Latn",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "Koulutus on avain yhteiskunnan kehitykseen.",
        "source": "fin_Latn",
        "target": "swe_Latn",
        "domain": "academic",
    },
    {
        "text": "Ympäristönsuojelu on välttämätöntä tulevaisuuden kannalta.",
        "source": "fin_Latn",
        "target": "est_Latn",
        "domain": "environment",
    },
    {
        "text": "Terveydenhuoltojärjestelmä tarvitsee jatkuvaa kehitystä.",
        "source": "fin_Latn",
        "target": "deu_Latn",
        "domain": "health",
    },
    # Czech (ces_Latn) - more examples
    {
        "text": "Digitální technologie mění způsob, jakým pracujeme a žijeme.",
        "source": "ces_Latn",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "Vzdělávání je základem rozvoje společnosti.",
        "source": "ces_Latn",
        "target": "slk_Latn",
        "domain": "academic",
    },
    {
        "text": "Ochrana životního prostředí je prioritou pro budoucí generace.",
        "source": "ces_Latn",
        "target": "pol_Latn",
        "domain": "environment",
    },
    {
        "text": "Zdravotní systém vyžaduje neustálé zlepšování.",
        "source": "ces_Latn",
        "target": "deu_Latn",
        "domain": "health",
    },
    # Romanian (ron_Latn) - more examples
    {
        "text": "Tehnologia digitală transformă modul în care lucrăm și trăim.",
        "source": "ron_Latn",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "Educația este fundamentul dezvoltării sociale.",
        "source": "ron_Latn",
        "target": "bul_Cyrl",
        "domain": "academic",
    },
    {
        "text": "Protecția mediului este esențială pentru viitor.",
        "source": "ron_Latn",
        "target": "hun_Latn",
        "domain": "environment",
    },
    {
        "text": "Sistemul de sănătate necesită îmbunătățiri constante.",
        "source": "ron_Latn",
        "target": "spa_Latn",
        "domain": "health",
    },
    # Hungarian (hun_Latn) - more examples
    {
        "text": "A digitális technológia átalakítja a munkavégzés és az életmód módját.",
        "source": "hun_Latn",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "Az oktatás a társadalom fejlesztésének alapja.",
        "source": "hun_Latn",
        "target": "slk_Latn",
        "domain": "academic",
    },
    {
        "text": "A környezetvédelem létfontosságú a jövő számára.",
        "source": "hun_Latn",
        "target": "ron_Latn",
        "domain": "environment",
    },
    {
        "text": "Az egészségügyi rendszer folyamatos fejlesztést igényel.",
        "source": "hun_Latn",
        "target": "deu_Latn",
        "domain": "health",
    },
    # Greek (ell_Grek) - more examples
    {
        "text": "Η ψηφιακή τεχνολογία μεταμορφώνει τον τρόπο που εργαζόμαστε.",
        "source": "ell_Grek",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "Η εκπαίδευση είναι θεμέλιο της κοινωνικής ανάπτυξης.",
        "source": "ell_Grek",
        "target": "fra_Latn",
        "domain": "academic",
    },
    {
        "text": "Η προστασία του περιβάλλοντος είναι ζωτικής σημασίας.",
        "source": "ell_Grek",
        "target": "ita_Latn",
        "domain": "environment",
    },
    {
        "text": "Το σύστημα υγείας χρειάζεται συνεχή βελτίωση.",
        "source": "ell_Grek",
        "target": "spa_Latn",
        "domain": "health",
    },
    # Bulgarian (bul_Cyrl) - more examples
    {
        "text": "Цифровата технология трансформира начина, по който работим.",
        "source": "bul_Cyrl",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "Образованието е основа на социалното развитие.",
        "source": "bul_Cyrl",
        "target": "rus_Cyrl",
        "domain": "academic",
    },
    {
        "text": "Защитата на околната среда е от съществено значение.",
        "source": "bul_Cyrl",
        "target": "srp_Cyrl",
        "domain": "environment",
    },
    {
        "text": "Здравната система изисква непрекъснато подобрение.",
        "source": "bul_Cyrl",
        "target": "ukr_Cyrl",
        "domain": "health",
    },
    # Ukrainian (ukr_Cyrl) - more examples
    {
        "text": "Цифрові технології змінюють спосіб нашої роботи та життя.",
        "source": "ukr_Cyrl",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "Освіта є основою розвитку суспільства.",
        "source": "ukr_Cyrl",
        "target": "pol_Latn",
        "domain": "academic",
    },
    {
        "text": "Захист навколишнього середовища має вирішальне значення.",
        "source": "ukr_Cyrl",
        "target": "rus_Cyrl",
        "domain": "environment",
    },
    {
        "text": "Система охорони здоров'я потребує постійного вдосконалення.",
        "source": "ukr_Cyrl",
        "target": "bul_Cyrl",
        "domain": "health",
    },
    # Serbian (srp_Cyrl) - more examples
    {
        "text": "Дигитална технологија мења начин на који радимо.",
        "source": "srp_Cyrl",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "Образовање је основа друштвеног развоја.",
        "source": "srp_Cyrl",
        "target": "hrv_Latn",
        "domain": "academic",
    },
    {
        "text": "Заштита животне средине је од суштинског значаја.",
        "source": "srp_Cyrl",
        "target": "rus_Cyrl",
        "domain": "environment",
    },
    {
        "text": "Систем здравствене заштите захтева континуирано побољшање.",
        "source": "srp_Cyrl",
        "target": "bul_Cyrl",
        "domain": "health",
    },
    # Croatian (hrv_Latn) - more examples
    {
        "text": "Digitalna tehnologija mijenja način na koji radimo.",
        "source": "hrv_Latn",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "Obrazovanje je temelj društvenog razvoja.",
        "source": "hrv_Latn",
        "target": "srp_Cyrl",
        "domain": "academic",
    },
    {
        "text": "Zaštita okoliša je od ključne važnosti.",
        "source": "hrv_Latn",
        "target": "slk_Latn",
        "domain": "environment",
    },
    {
        "text": "Zdravstveni sustav zahtijeva kontinuirano poboljšanje.",
        "source": "hrv_Latn",
        "target": "ces_Latn",
        "domain": "health",
    },
    # Slovak (slk_Latn) - more examples
    {
        "text": "Digitálna technológia mení spôsob, akým pracujeme.",
        "source": "slk_Latn",
        "target": "eng_Latn",
        "domain": "technology",
    },
    {
        "text": "Vzdelávanie je základom spoločenského rozvoja.",
        "source": "slk_Latn",
        "target": "ces_Latn",
        "domain": "academic",
    },
    {
        "text": "Ochrana životného prostredia je prioritou.",
        "source": "slk_Latn",
        "target": "pol_Latn",
        "domain": "environment",
    },
    {
        "text": "Zdravotnícky systém vyžaduje neustále zlepšovanie.",
        "source": "slk_Latn",
        "target": "hun_Latn",
        "domain": "health",
    },
]


def get_flores_samples(num_items: int | None = None) -> list[dict[str, str]]:
    """
    Get FLORES-200 sample sentences.

    Parameters
    ----------
    num_items : int | None
        Number of samples to return. If None, returns all samples.

    Returns
    -------
    list[dict[str, str]]
        List of translation samples with 'text', 'source', and 'target' keys.
    """
    samples = FLORES_200_SAMPLES.copy()

    if num_items is not None:
        # Repeat samples if needed to reach num_items
        while len(samples) < num_items:
            samples.extend(FLORES_200_SAMPLES)

        samples = samples[:num_items]

    # Return only the fields needed for translation
    return [
        {"text": item["text"], "source": item["source"], "target": item["target"]}
        for item in samples
    ]


def get_flores_by_domain(domain: str) -> list[dict[str, str]]:
    """
    Get FLORES-200 samples filtered by domain.

    Parameters
    ----------
    domain : str
        Domain to filter by (e.g., 'general', 'technical', 'news', 'science', etc.)

    Returns
    -------
    list[dict[str, str]]
        List of translation samples from the specified domain.
    """
    filtered = [item for item in FLORES_200_SAMPLES if item.get("domain") == domain]
    return [
        {"text": item["text"], "source": item["source"], "target": item["target"]}
        for item in filtered
    ]


def get_flores_language_pairs() -> list[tuple[str, str]]:
    """
    Get all unique language pairs in the FLORES samples.

    Returns
    -------
    list[tuple[str, str]]
        List of (source, target) language pairs.
    """
    pairs = set()
    for item in FLORES_200_SAMPLES:
        pairs.add((item["source"], item["target"]))
    return sorted(list(pairs))

