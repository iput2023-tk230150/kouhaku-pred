"""
アーティスト名正規化モジュール
==============================
アーティスト名を正規化し、複数のバリエーションを生成する機能を提供
"""

import re
import pykakasi


class ArtistNameNormalizer:
    """アーティスト名を正規化するクラス"""

    def __init__(self):
        self.kks = pykakasi.kakasi()

        # 旧字体→新字体の変換マップ（Google Trends対応）
        self.old_to_new_kanji = {
            "髙": "高",
            "德": "徳",
            "﨑": "崎",
            "濵": "浜",
            "邊": "辺",
            "邉": "辺",
            "齋": "斎",
            "齊": "斉",
            "國": "国",
            "廣": "広",
            "櫻": "桜",
            "澤": "沢",
            "藤": "藤",  # 異体字対応
            "眞": "真",
            "實": "実",
            "學": "学",
            "鷗": "鴎",
            "龍": "竜",
            "萬": "万",
            "壽": "寿",
            "靜": "静",
            "淵": "渕",
            "黑": "黒",
            "增": "増",
            "鐵": "鉄",
            "藝": "芸",
            "惠": "恵",
            "峯": "峰",
            "榮": "栄",
            "禮": "礼",
            "稀": "稀",
            "條": "条",
            "絲": "糸",
            "莊": "荘",
            "嶋": "島",
            "嶌": "島",
        }

        # 記号の置換ルール
        self.symbol_replacements = {
            "&": "AND",
            "＆": "AND",
            "+": "PLUS",
            "×": "X",
            "☆": "",
            "★": "",
            "♪": "",
            "・": "",
            "　": "",  # 全角スペース
            " ": "",  # 半角スペース
            "-": "",
            "_": "",
            ".": "",
            "'": "",
            '"': "",
            "!": "",
            "?": "",
            "~": "",
            "〜": "",
        }

        # 長音の正規化ルール(ヘボン式 → 簡略化)
        self.long_vowel_rules = [
            ("OU", "O"),  # おう → O (例: TOUKYOU → TOKYO)
            ("OO", "O"),  # おお → O
            ("UU", "U"),  # うう → U
            ("II", "I"),  # いい → I
            ("EI", "E"),  # えい → E (例: SENSEI → SENSE) ※これは微妙なので後で調整可能
            ("AA", "A"),  # ああ → A
        ]

    def to_romaji(self, text: str) -> str:
        """日本語をローマ字に変換"""
        result = self.kks.convert(text)
        return "".join([item["hepburn"] for item in result])

    def normalize_old_kanji(self, text: str) -> str:
        """旧字体・異体字を新字体に変換（Google Trends対応）"""
        result = text
        for old_char, new_char in self.old_to_new_kanji.items():
            result = result.replace(old_char, new_char)
        return result

    def normalize_for_search(self, name: str) -> str:
        """
        検索用に名前を正規化（Google Trends用）
        - 旧字体→新字体変換のみ
        - 元の表記を維持しつつ検索しやすくする
        """
        if not name:
            return ""
        return self.normalize_old_kanji(str(name))

    def normalize_long_vowels(self, text: str) -> str:
        """長音を正規化"""
        result = text
        for pattern, replacement in self.long_vowel_rules:
            result = result.replace(pattern, replacement)
        return result

    def normalize(self, name: str, apply_long_vowel: bool = True) -> str:
        """アーティスト名を正規化"""
        if not name or (
            hasattr(name, "__class__") and name.__class__.__name__ == "NAType"
        ):
            return ""

        normalized = str(name)

        # 1. 記号を置換
        for symbol, replacement in self.symbol_replacements.items():
            normalized = normalized.replace(symbol, replacement)

        # 2. ローマ字変換(日本語が含まれている場合)
        if self._contains_japanese(normalized):
            normalized = self.to_romaji(normalized)

        # 3. 大文字に統一
        normalized = normalized.upper()

        # 4. 長音の正規化(オプション)
        if apply_long_vowel:
            normalized = self.normalize_long_vowels(normalized)

        # 5. 英数字以外を除去
        normalized = re.sub(r"[^A-Z0-9]", "", normalized)

        return normalized

    def get_name_variants(self, name: str) -> list[str]:
        """
        アーティスト名の複数バリエーションを生成
        - 通常の正規化
        - 長音正規化なし
        - 姓名逆転(日本人名の場合)
        """
        variants = set()

        # 基本の正規化
        base = self.normalize(name, apply_long_vowel=True)
        if base:
            variants.add(base)

        # 長音正規化なしバージョン
        no_long_vowel = self.normalize(name, apply_long_vowel=False)
        if no_long_vowel:
            variants.add(no_long_vowel)

        # 姓名逆転パターン(日本語名の場合)
        if self._is_japanese_name(name):
            reversed_variants = self._generate_reversed_name_variants(name)
            variants.update(reversed_variants)

        return list(variants)

    def _contains_japanese(self, text: str) -> bool:
        """日本語(ひらがな・カタカナ・漢字)が含まれるか判定"""
        return bool(re.search(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]", text))

    def _is_japanese_name(self, name: str) -> bool:
        """日本人名らしいか判定(日本語文字2文字以上)"""
        japanese_chars = re.sub(r"[^\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]", "", name)
        return 2 <= len(japanese_chars) <= 10

    def _generate_reversed_name_variants(self, name: str) -> list[str]:
        """
        姓名逆転のバリエーションを生成
        例: 米津玄師 → [KENSHIYONEZU]
            宇多田ヒカル → [HIKARUUTADA]
        """
        variants = []

        # 日本語部分を抽出(漢字・ひらがな・カタカナ)
        japanese_part = re.sub(r"[^\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]", "", name)

        if len(japanese_part) < 2:
            return variants

        # 様々な分割位置で姓名逆転を試行
        for split_pos in range(1, len(japanese_part)):
            first_part = japanese_part[:split_pos]
            second_part = japanese_part[split_pos:]

            if len(first_part) >= 1 and len(second_part) >= 1:
                # 姓名逆転(名+姓の順)
                reversed_name = second_part + first_part

                # ローマ字変換して正規化
                romaji_reversed = self.to_romaji(reversed_name).upper()
                romaji_reversed = self.normalize_long_vowels(romaji_reversed)
                romaji_reversed = re.sub(r"[^A-Z0-9]", "", romaji_reversed)

                if romaji_reversed:
                    variants.append(romaji_reversed)

        return variants
