"""
コア関数のユニットテスト
========================
リファクタリング前の動作を保証するためのテスト
"""

import pytest
from datetime import date
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from collectors.step1_get_song_list import clean_number
from collectors.step2_get_weekly_data import parse_jp_value
from core.pipeline import get_fiscal_year_boundary


class TestCleanNumber:
    """clean_number() のテスト"""

    def test_clean_number_with_comma(self):
        """カンマ区切りの数値文字列"""
        assert clean_number("1,234,567") == 1234567

    def test_clean_number_plain(self):
        """カンマなし数値文字列"""
        assert clean_number("12345") == 12345

    def test_clean_number_empty(self):
        """空文字列"""
        assert clean_number("") == 0

    def test_clean_number_none(self):
        """None"""
        assert clean_number(None) == 0

    def test_clean_number_with_non_numeric(self):
        """数値以外の文字を含む"""
        assert clean_number("abc123def") == 123


class TestParseJpValue:
    """parse_jp_value() のテスト"""

    def test_parse_jp_value_normal(self):
        """通常の形式: '1(26,291)'"""
        rank, streams = parse_jp_value("1(26,291)")
        assert rank == 1
        assert streams == 26291

    def test_parse_jp_value_large_number(self):
        """大きな数値: '5(1,234,567)'"""
        rank, streams = parse_jp_value("5(1,234,567)")
        assert rank == 5
        assert streams == 1234567

    def test_parse_jp_value_no_data(self):
        """データなし: '--'"""
        rank, streams = parse_jp_value("--")
        assert rank is None
        assert streams is None

    def test_parse_jp_value_empty(self):
        """空文字列"""
        rank, streams = parse_jp_value("")
        assert rank is None
        assert streams is None

    def test_parse_jp_value_rank_only(self):
        """順位のみ: '10'"""
        rank, streams = parse_jp_value("10")
        assert rank == 10
        assert streams is None


class TestGetFiscalYearBoundary:
    """get_fiscal_year_boundary() のテスト"""

    def test_fiscal_year_boundary_2024(self):
        """2024年の境界日（11月第4週木曜日）"""
        boundary = get_fiscal_year_boundary(2024)
        # 2024年11月1日は金曜日
        # 最初の木曜日は11月7日
        # 第4木曜日は11月28日
        assert boundary == date(2024, 11, 28)

    def test_fiscal_year_boundary_2023(self):
        """2023年の境界日"""
        boundary = get_fiscal_year_boundary(2023)
        # 2023年11月1日は水曜日
        # 最初の木曜日は11月2日
        # 第4木曜日は11月23日
        assert boundary == date(2023, 11, 23)

    def test_fiscal_year_boundary_2025(self):
        """2025年の境界日"""
        boundary = get_fiscal_year_boundary(2025)
        # 2025年11月1日は土曜日
        # 最初の木曜日は11月6日
        # 第4木曜日は11月27日
        assert boundary == date(2025, 11, 27)

    def test_fiscal_year_boundary_is_thursday(self):
        """境界日が必ず木曜日であることを確認"""
        for year in range(2020, 2026):
            boundary = get_fiscal_year_boundary(year)
            # 木曜日 = 3
            assert boundary.weekday() == 3, f"{year}年の境界日が木曜日ではありません"

    def test_fiscal_year_boundary_in_november(self):
        """境界日が必ず11月であることを確認"""
        for year in range(2020, 2026):
            boundary = get_fiscal_year_boundary(year)
            assert boundary.month == 11, f"{year}年の境界日が11月ではありません"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
