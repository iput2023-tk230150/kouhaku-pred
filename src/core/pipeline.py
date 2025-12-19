"""
パイプライン基底クラス
======================
各Stepスクリプトの共通インターフェース
"""

from abc import ABC, abstractmethod
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import tomllib


class DataPipeline(ABC):
    """データ収集パイプラインの基底クラス"""

    def __init__(self, config: dict[str, Any], data_dir: Path):
        """
        Args:
            config: 設定辞書
            data_dir: データ出力ディレクトリ
        """
        self.config = config
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def execute(self) -> bool:
        """
        パイプラインステップを実行

        Returns:
            成功時True、失敗時False
        """
        pass

    @abstractmethod
    def get_output_files(self) -> list[Path]:
        """
        このステップが出力するファイルのリストを返す

        Returns:
            出力ファイルパスのリスト
        """
        pass

    def check_dependencies(self) -> tuple[bool, list[str]]:
        """
        依存ファイルの存在チェック

        Returns:
            (すべて存在するか, 不足ファイルのリスト)
        """
        return True, []

    def validate_outputs(self) -> tuple[bool, list[str]]:
        """
        出力ファイルが正しく生成されたかチェック

        Returns:
            (すべて存在するか, 不足ファイルのリスト)
        """
        missing = []
        for file_path in self.get_output_files():
            if not file_path.exists():
                missing.append(str(file_path))

        return len(missing) == 0, missing


def get_fiscal_year_boundary(year: int) -> date:
    """
    指定年の11月第4週木曜日（年度境界日）を取得

    kworb.netは木曜始まりのため、木曜日を境界とする。
    ビルボードジャパンの年間チャート集計期間に準拠:
    例: 2025年チャート = 2024年11月25日〜2025年11月23日

    Args:
        year: 対象年

    Returns:
        11月第4週木曜日の日付
    """
    nov_1 = date(year, 11, 1)
    # 11月1日から最初の木曜日を探す（木曜=3）
    days_until_thursday = (3 - nov_1.weekday()) % 7
    first_thursday = nov_1 + timedelta(days=days_until_thursday)
    # 第4木曜日 = 最初の木曜日 + 3週間
    fourth_thursday = first_thursday + timedelta(weeks=3)
    return fourth_thursday


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """
    設定ファイルを読み込む

    Args:
        config_path: 設定ファイルのパス（Noneの場合はデフォルト）

    Returns:
        設定辞書
    """
    if config_path is None:
        # デフォルトパス: プロジェクトルート/config.toml
        # src/core/pipeline.py → src/core → src → プロジェクトルート
        config_path = Path(__file__).parent.parent.parent / "config.toml"

    if not config_path.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}")

    with open(config_path, "rb") as f:
        return tomllib.load(f)
