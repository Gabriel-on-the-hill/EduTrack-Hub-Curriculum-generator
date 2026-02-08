"""
Multilingual Synthetic Curricula (Phase 4 Deferred Item #14)

Provides support for generating synthetic curricula in multiple languages
to test internationalization handling in the extraction pipeline.

Features:
- Language-specific topic translations
- Character set testing (Latin, Cyrillic, CJK, Arabic, etc.)
- Mixed-language documents
- RTL text handling
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class SupportedLanguage(str, Enum):
    """Languages supported for synthetic curriculum generation."""
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    PORTUGUESE = "pt"
    ARABIC = "ar"
    CHINESE_SIMPLIFIED = "zh-CN"
    CHINESE_TRADITIONAL = "zh-TW"
    JAPANESE = "ja"
    KOREAN = "ko"
    RUSSIAN = "ru"
    HINDI = "hi"


@dataclass
class LanguageCharacteristics:
    """Characteristics of a language for testing."""
    code: str
    name: str
    native_name: str
    script: str  # latin, cyrillic, cjk, arabic, devanagari
    direction: str  # ltr or rtl
    has_diacritics: bool
    sample_chars: str  # Sample unique characters


# Language metadata for testing
LANGUAGE_METADATA: dict[SupportedLanguage, LanguageCharacteristics] = {
    SupportedLanguage.ENGLISH: LanguageCharacteristics(
        code="en", name="English", native_name="English",
        script="latin", direction="ltr", has_diacritics=False,
        sample_chars="ABCDEFGabcdefg",
    ),
    SupportedLanguage.SPANISH: LanguageCharacteristics(
        code="es", name="Spanish", native_name="Español",
        script="latin", direction="ltr", has_diacritics=True,
        sample_chars="ñÑáéíóúüÁÉÍÓÚÜ",
    ),
    SupportedLanguage.FRENCH: LanguageCharacteristics(
        code="fr", name="French", native_name="Français",
        script="latin", direction="ltr", has_diacritics=True,
        sample_chars="àâäéèêëïîôùûüÿç",
    ),
    SupportedLanguage.GERMAN: LanguageCharacteristics(
        code="de", name="German", native_name="Deutsch",
        script="latin", direction="ltr", has_diacritics=True,
        sample_chars="äöüßÄÖÜ",
    ),
    SupportedLanguage.PORTUGUESE: LanguageCharacteristics(
        code="pt", name="Portuguese", native_name="Português",
        script="latin", direction="ltr", has_diacritics=True,
        sample_chars="ãõáéíóúâêôàç",
    ),
    SupportedLanguage.ARABIC: LanguageCharacteristics(
        code="ar", name="Arabic", native_name="العربية",
        script="arabic", direction="rtl", has_diacritics=True,
        sample_chars="العربية مرحبا",
    ),
    SupportedLanguage.CHINESE_SIMPLIFIED: LanguageCharacteristics(
        code="zh-CN", name="Chinese (Simplified)", native_name="简体中文",
        script="cjk", direction="ltr", has_diacritics=False,
        sample_chars="你好世界生物学",
    ),
    SupportedLanguage.CHINESE_TRADITIONAL: LanguageCharacteristics(
        code="zh-TW", name="Chinese (Traditional)", native_name="繁體中文",
        script="cjk", direction="ltr", has_diacritics=False,
        sample_chars="你好世界生物學",
    ),
    SupportedLanguage.JAPANESE: LanguageCharacteristics(
        code="ja", name="Japanese", native_name="日本語",
        script="cjk", direction="ltr", has_diacritics=False,
        sample_chars="こんにちは生物学",
    ),
    SupportedLanguage.KOREAN: LanguageCharacteristics(
        code="ko", name="Korean", native_name="한국어",
        script="hangul", direction="ltr", has_diacritics=False,
        sample_chars="안녕하세요생물학",
    ),
    SupportedLanguage.RUSSIAN: LanguageCharacteristics(
        code="ru", name="Russian", native_name="Русский",
        script="cyrillic", direction="ltr", has_diacritics=False,
        sample_chars="АБВГДабвгд",
    ),
    SupportedLanguage.HINDI: LanguageCharacteristics(
        code="hi", name="Hindi", native_name="हिन्दी",
        script="devanagari", direction="ltr", has_diacritics=True,
        sample_chars="नमस्ते जीवविज्ञान",
    ),
}


# =============================================================================
# TOPIC TRANSLATIONS
# =============================================================================

# Common biology topics translated to supported languages
BIOLOGY_TOPIC_TRANSLATIONS: dict[str, dict[SupportedLanguage, str]] = {
    "Cell Structure": {
        SupportedLanguage.ENGLISH: "Cell Structure",
        SupportedLanguage.SPANISH: "Estructura Celular",
        SupportedLanguage.FRENCH: "Structure Cellulaire",
        SupportedLanguage.GERMAN: "Zellstruktur",
        SupportedLanguage.PORTUGUESE: "Estrutura Celular",
        SupportedLanguage.ARABIC: "بنية الخلية",
        SupportedLanguage.CHINESE_SIMPLIFIED: "细胞结构",
        SupportedLanguage.JAPANESE: "細胞構造",
        SupportedLanguage.KOREAN: "세포 구조",
        SupportedLanguage.RUSSIAN: "Клеточная структура",
    },
    "Cell Division": {
        SupportedLanguage.ENGLISH: "Cell Division",
        SupportedLanguage.SPANISH: "División Celular",
        SupportedLanguage.FRENCH: "Division Cellulaire",
        SupportedLanguage.GERMAN: "Zellteilung",
        SupportedLanguage.PORTUGUESE: "Divisão Celular",
        SupportedLanguage.ARABIC: "انقسام الخلية",
        SupportedLanguage.CHINESE_SIMPLIFIED: "细胞分裂",
        SupportedLanguage.JAPANESE: "細胞分裂",
        SupportedLanguage.KOREAN: "세포 분열",
        SupportedLanguage.RUSSIAN: "Клеточное деление",
    },
    "Photosynthesis": {
        SupportedLanguage.ENGLISH: "Photosynthesis",
        SupportedLanguage.SPANISH: "Fotosíntesis",
        SupportedLanguage.FRENCH: "Photosynthèse",
        SupportedLanguage.GERMAN: "Photosynthese",
        SupportedLanguage.PORTUGUESE: "Fotossíntese",
        SupportedLanguage.ARABIC: "التمثيل الضوئي",
        SupportedLanguage.CHINESE_SIMPLIFIED: "光合作用",
        SupportedLanguage.JAPANESE: "光合成",
        SupportedLanguage.KOREAN: "광합성",
        SupportedLanguage.RUSSIAN: "Фотосинтез",
    },
    "Genetics": {
        SupportedLanguage.ENGLISH: "Genetics",
        SupportedLanguage.SPANISH: "Genética",
        SupportedLanguage.FRENCH: "Génétique",
        SupportedLanguage.GERMAN: "Genetik",
        SupportedLanguage.PORTUGUESE: "Genética",
        SupportedLanguage.ARABIC: "علم الوراثة",
        SupportedLanguage.CHINESE_SIMPLIFIED: "遗传学",
        SupportedLanguage.JAPANESE: "遺伝学",
        SupportedLanguage.KOREAN: "유전학",
        SupportedLanguage.RUSSIAN: "Генетика",
    },
    "Evolution": {
        SupportedLanguage.ENGLISH: "Evolution",
        SupportedLanguage.SPANISH: "Evolución",
        SupportedLanguage.FRENCH: "Évolution",
        SupportedLanguage.GERMAN: "Evolution",
        SupportedLanguage.PORTUGUESE: "Evolução",
        SupportedLanguage.ARABIC: "التطور",
        SupportedLanguage.CHINESE_SIMPLIFIED: "进化",
        SupportedLanguage.JAPANESE: "進化",
        SupportedLanguage.KOREAN: "진화",
        SupportedLanguage.RUSSIAN: "Эволюция",
    },
}


@dataclass
class MultilingualTopicConfig:
    """Configuration for multilingual topic generation."""
    primary_language: SupportedLanguage = SupportedLanguage.ENGLISH
    include_translations: bool = False
    translation_languages: list[SupportedLanguage] = field(default_factory=list)
    mix_languages_in_document: bool = False  # For testing mixed-language extraction


class MultilingualTopicTranslator:
    """
    Translates topic titles between languages.
    
    Uses static translation tables for common topics,
    with fallback to original title if translation unavailable.
    """
    
    def __init__(self, translation_table: dict[str, dict[SupportedLanguage, str]] | None = None):
        """Initialize with optional custom translation table."""
        self._translations = translation_table or BIOLOGY_TOPIC_TRANSLATIONS
    
    def translate(
        self,
        topic_title: str,
        target_language: SupportedLanguage,
    ) -> str:
        """
        Translate a topic title to target language.
        
        Returns original title if translation not available.
        """
        if topic_title in self._translations:
            translations = self._translations[topic_title]
            if target_language in translations:
                return translations[target_language]
        
        # Fallback: return original
        return topic_title
    
    def get_all_translations(
        self,
        topic_title: str,
    ) -> dict[SupportedLanguage, str]:
        """Get all available translations for a topic."""
        if topic_title in self._translations:
            return self._translations[topic_title].copy()
        return {SupportedLanguage.ENGLISH: topic_title}
    
    def has_translation(
        self,
        topic_title: str,
        language: SupportedLanguage,
    ) -> bool:
        """Check if translation exists for topic in language."""
        return (
            topic_title in self._translations and
            language in self._translations[topic_title]
        )


# =============================================================================
# MULTILINGUAL CURRICULUM GENERATOR
# =============================================================================

@dataclass
class MultilingualCurriculumConfig:
    """Configuration for multilingual curriculum generation."""
    base_language: SupportedLanguage = SupportedLanguage.ENGLISH
    target_language: SupportedLanguage = SupportedLanguage.ENGLISH
    include_parallel_text: bool = False  # Side-by-side translations
    test_character_encoding: bool = True  # Include special chars
    test_mixed_scripts: bool = False  # Mix multiple scripts


class MultilingualCurriculumGenerator:
    """
    Generates synthetic curricula in multiple languages.
    
    Used to test:
    - UTF-8 encoding handling
    - RTL text extraction
    - CJK character recognition
    - Diacritic preservation
    """
    
    def __init__(self, config: MultilingualCurriculumConfig | None = None):
        """Initialize with configuration."""
        self.config = config or MultilingualCurriculumConfig()
        self.translator = MultilingualTopicTranslator()
    
    def generate_translated_content(
        self,
        original_markdown: str,
        topics: list[str],
    ) -> str:
        """
        Generate curriculum content in target language.
        
        Translates topic titles and basic structure words.
        """
        content = original_markdown
        target = self.config.target_language
        
        # Translate topic titles
        for topic in topics:
            translated = self.translator.translate(topic, target)
            content = content.replace(topic, translated)
        
        # Add language metadata header
        lang_info = LANGUAGE_METADATA.get(target)
        if lang_info:
            header = f"<!-- Language: {lang_info.name} ({lang_info.native_name}) -->\n"
            content = header + content
        
        return content
    
    def generate_parallel_text(
        self,
        topics: list[str],
        languages: list[SupportedLanguage],
    ) -> str:
        """
        Generate parallel text with topics in multiple languages.
        
        Useful for testing multilingual extraction accuracy.
        """
        lines = ["# Parallel Text Test Document\n"]
        
        for topic in topics:
            lines.append(f"\n## {topic}")
            for lang in languages:
                translated = self.translator.translate(topic, lang)
                lang_info = LANGUAGE_METADATA.get(lang)
                if lang_info:
                    lines.append(f"- **{lang_info.name}**: {translated}")
            lines.append("")
        
        return "\n".join(lines)
    
    def generate_character_test(
        self,
        languages: list[SupportedLanguage] | None = None,
    ) -> str:
        """
        Generate document with special characters from multiple scripts.
        
        Tests character encoding and OCR handling.
        """
        if languages is None:
            languages = list(LANGUAGE_METADATA.keys())
        
        lines = ["# Character Encoding Test Document\n"]
        
        for lang in languages:
            info = LANGUAGE_METADATA.get(lang)
            if info:
                lines.append(f"## {info.name} ({info.script})")
                lines.append(f"- Native name: {info.native_name}")
                lines.append(f"- Sample characters: {info.sample_chars}")
                lines.append(f"- Direction: {info.direction}")
                lines.append("")
        
        return "\n".join(lines)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_language_info(language: SupportedLanguage) -> LanguageCharacteristics | None:
    """Get characteristics for a language."""
    return LANGUAGE_METADATA.get(language)


def get_rtl_languages() -> list[SupportedLanguage]:
    """Get list of RTL languages."""
    return [
        lang for lang, info in LANGUAGE_METADATA.items()
        if info.direction == "rtl"
    ]


def get_cjk_languages() -> list[SupportedLanguage]:
    """Get list of CJK languages."""
    return [
        lang for lang, info in LANGUAGE_METADATA.items()
        if info.script == "cjk"
    ]


def translate_topic(
    topic: str,
    target_language: SupportedLanguage,
) -> str:
    """Convenience function to translate a single topic."""
    translator = MultilingualTopicTranslator()
    return translator.translate(topic, target_language)
