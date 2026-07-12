"""Adapter = 모델 하나를 로드해서 (prompt, negative, seed) -> PIL.Image 함수로 만든다.

모델마다 conda env가 다르므로, 활성 모델의 adapter만 lazy import한다.
(전부 import하면 어느 env에서 돌리든 다른 모델의 diffusers 버전 요구에서 터짐)
"""
import importlib


def load(model_cfg):
    mod = importlib.import_module(f"adapters.{model_cfg['adapter']}")
    return mod.build(model_cfg)
