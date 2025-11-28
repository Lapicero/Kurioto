"""
Kurioto: A Safe AI Companion for Curious Minds

This package implements a cloud-based AI agent designed specifically for children's
educational needs, featuring multi-step reasoning, tool integration, memory management,
and comprehensive safety governance.
"""

__version__ = "0.1.0"
__author__ = "Lapicero"

from kurioto.agent import KuriotoAgent
from kurioto.config import Settings

__all__ = ["KuriotoAgent", "Settings", "__version__"]
