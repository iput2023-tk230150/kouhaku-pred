"""
Collectors モジュール
=====================
データ収集パイプライン（Step1〜4）
"""

from .step1_get_song_list import Step1Pipeline
from .step2_get_weekly_data import Step2Pipeline
from .step3_get_kouhaku_artists import Step3Pipeline
from .step4_get_google_trends import Step4Pipeline

__all__ = ["Step1Pipeline", "Step2Pipeline", "Step3Pipeline", "Step4Pipeline"]
