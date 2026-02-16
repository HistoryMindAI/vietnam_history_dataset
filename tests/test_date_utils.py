"""
test_date_utils.py — Unit Tests for safe_year()

Tests the centralized date utility used across
search_service.py, engine.py, answer_synthesis.py.

Covers: None, "", bool, list, dict, "invalid", extreme values.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ai-service'))

from app.core.utils.date_utils import safe_year


# ===================================================================
# 1. BASIC VALID INPUTS
# ===================================================================

def test_safe_year_valid_int():
    assert safe_year(938) == 938


def test_safe_year_valid_string():
    assert safe_year("938") == 938


def test_safe_year_zero():
    assert safe_year(0) == 0


def test_safe_year_negative_bce():
    """BCE years are valid when allow_negative=True (default)."""
    assert safe_year(-500) == -500


# ===================================================================
# 2. CORRUPT / INVALID INPUTS
# ===================================================================

def test_safe_year_none():
    assert safe_year(None) == 9999


def test_safe_year_empty_string():
    assert safe_year("") == 9999


def test_safe_year_invalid_string():
    assert safe_year("invalid") == 9999


def test_safe_year_list():
    assert safe_year([]) == 9999


def test_safe_year_dict():
    assert safe_year({}) == 9999


def test_safe_year_bool_true():
    """bool is subclass of int — True would be 1 without guard."""
    assert safe_year(True) == 9999


def test_safe_year_bool_false():
    """bool is subclass of int — False would be 0 without guard."""
    assert safe_year(False) == 9999


def test_safe_year_float():
    """float should be truncated to int."""
    assert safe_year(938.7) == 938


# ===================================================================
# 3. CUSTOM DEFAULT
# ===================================================================

def test_safe_year_custom_default():
    assert safe_year(None, default=0) == 0


def test_safe_year_custom_default_invalid():
    assert safe_year("xyz", default=-1) == -1


# ===================================================================
# 4. NEGATIVE YEAR GUARD
# ===================================================================

def test_safe_year_negative_not_allowed():
    assert safe_year(-500, allow_negative=False) == 9999


def test_safe_year_negative_allowed():
    assert safe_year(-500, allow_negative=True) == -500


# ===================================================================
# 5. MAX YEAR CLAMP
# ===================================================================

def test_safe_year_max_clamp():
    assert safe_year(999999999, max_year=3000) == 9999


def test_safe_year_within_max():
    assert safe_year(2025, max_year=3000) == 2025


def test_safe_year_extreme_negative():
    assert safe_year(-999999) == -999999
