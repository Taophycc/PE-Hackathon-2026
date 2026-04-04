"""
Bronze / Unit Tests — Individual function isolation.

Tests generate_short_code() in complete isolation: no database, no Flask
app, no fixtures. Input A → Output B only.
"""
import string

from app.models.link import generate_short_code


class TestGenerateShortCode:
    def test_default_length_is_six(self):
        assert len(generate_short_code()) == 6

    def test_custom_length_is_respected(self):
        assert len(generate_short_code(length=10)) == 10
        assert len(generate_short_code(length=1)) == 1

    def test_zero_length_returns_empty_string(self):
        assert generate_short_code(length=0) == ""

    def test_characters_are_alphanumeric_only(self):
        valid = set(string.ascii_letters + string.digits)
        for _ in range(50):
            code = generate_short_code()
            assert all(c in valid for c in code), f"Invalid char in: {code}"

    def test_returns_string(self):
        assert isinstance(generate_short_code(), str)

    def test_generates_different_codes(self):
        """
        With a 62-character alphabet and length=6, there are 62^6 ≈ 56 billion
        possible codes. The probability of 100 consecutive identical codes is
        negligible — this asserts randomness without being flaky.
        """
        codes = {generate_short_code() for _ in range(100)}
        assert len(codes) > 1
