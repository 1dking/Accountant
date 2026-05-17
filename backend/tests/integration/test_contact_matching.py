"""Bug #6 regression: NANP phone normalization in contact matching.

Symptom (2026-05-17): inbound SMS from '+12896984168' didn't match
contact with phone='2896984168'. _strip_non_digits produced 11 vs 10
digit comparison, equality failed, contact_id stayed NULL, conversation
engine never fired.

This unit-level test exercises _strip_non_digits directly. No HTTP,
no DB needed.
"""
from app.communication.service import _strip_non_digits


class TestStripNonDigitsNANP:
    def test_strips_plus_and_country_code(self):
        """The smoking-gun case from the live bug."""
        assert _strip_non_digits("+12896984168") == "2896984168"
        assert _strip_non_digits("2896984168") == "2896984168"
        # These should compare equal (proving the fix)
        assert _strip_non_digits("+12896984168") == _strip_non_digits("2896984168")

    def test_handles_formatting_variants(self):
        assert _strip_non_digits("(289) 698-4168") == "2896984168"
        assert _strip_non_digits("289-698-4168") == "2896984168"
        assert _strip_non_digits("289.698.4168") == "2896984168"
        assert _strip_non_digits("+1 (289) 698-4168") == "2896984168"

    def test_non_nanp_unaffected(self):
        # UK +44 1234 567890 has 12 digits after strip — NOT 11 — so
        # we don't strip the leading 4 (correct, since it's not a 1).
        assert _strip_non_digits("+44 1234 567890") == "441234567890"
        # AU +61 4 1234 5678 (mobile, 11 digits total including +61)
        # 11 digits but doesn't start with 1 — no strip.
        assert _strip_non_digits("+61412345678") == "61412345678"

    def test_eleven_digits_starting_with_one_strips(self):
        """The NANP normalization rule: 11 digits + leading 1 → strip the 1."""
        assert _strip_non_digits("12896984168") == "2896984168"
        assert _strip_non_digits("14165550000") == "4165550000"

    def test_eleven_digits_NOT_starting_with_one_preserved(self):
        """Edge: 11-digit number starting with non-1 stays intact."""
        # Hypothetical 11-digit number starting with 2 — keep all 11
        assert _strip_non_digits("28968412345") == "28968412345"

    def test_empty_and_garbage_input(self):
        assert _strip_non_digits("") == ""
        assert _strip_non_digits("abc") == ""
        assert _strip_non_digits("!!!") == ""
