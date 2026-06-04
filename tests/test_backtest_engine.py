"""Unit tests for backtest engine — weekday helper and smoke test"""

import pytest
from backtest.engine import _weekday_from_name


class TestWeekdayFromName:
    def test_chinese(self):
        assert _weekday_from_name("周三") == 2

    def test_english_full(self):
        assert _weekday_from_name("wednesday") == 2

    def test_english_short(self):
        assert _weekday_from_name("Wed") == 2

    def test_monday(self):
        assert _weekday_from_name("周一") == 0
        assert _weekday_from_name("monday") == 0
        assert _weekday_from_name("Mon") == 0

    def test_sunday(self):
        assert _weekday_from_name("周日") == 6
        assert _weekday_from_name("sunday") == 6
        assert _weekday_from_name("Sun") == 6

    def test_unknown(self):
        assert _weekday_from_name("foo") == -1

    def test_case_insensitive(self):
        assert _weekday_from_name("WEDNESDAY") == 2
        assert _weekday_from_name("WED") == 2

    def test_whitespace(self):
        assert _weekday_from_name("  Wed  ") == 2
