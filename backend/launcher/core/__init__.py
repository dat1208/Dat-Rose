#!/usr/bin/env python3
"""
Core launcher package
Contains the main launcher entry point
"""

from ..updater import auto_update
from .launcher import run_launcher

__all__ = ['auto_update', 'run_launcher']

