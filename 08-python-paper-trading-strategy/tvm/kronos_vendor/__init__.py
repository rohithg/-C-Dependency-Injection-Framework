"""Vendored copy of the Kronos model code (MIT, (c) 2025 ShiYu).

Source: https://github.com/shiyu-coder/Kronos  (model/kronos.py, model/module.py)
The upstream repo is not packaged for pip, so the two inference files are
copied here verbatim apart from the import of `module` being made relative.
Pretrained weights are downloaded from the Hugging Face Hub on first use.
"""
from .kronos import Kronos, KronosTokenizer, KronosPredictor

__all__ = ["Kronos", "KronosTokenizer", "KronosPredictor"]
