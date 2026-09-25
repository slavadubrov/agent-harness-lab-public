"""Resolve "package.module:attribute" references used in spec files."""

from __future__ import annotations

import importlib
from typing import Any


def import_ref(ref: str) -> Any:
    module, sep, attr = ref.partition(":")
    if not sep or not attr:
        raise ValueError(f"Reference {ref!r} must look like 'package.module:attribute'")
    obj: Any = importlib.import_module(module)
    for part in attr.split("."):
        obj = getattr(obj, part)
    return obj
