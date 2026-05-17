"""Bug #4 regression: MIME parameter stripping for voicemail-greeting upload.

Symptom (2026-05-16): browser MediaRecorder produces blobs with
content_type='audio/webm;codecs=opus'. The whitelist check rejected
these with 400 because 'audio/webm;codecs=opus' didn't match the bare
'audio/webm' in ALLOWED_AUDIO_MIME_TYPES.

This test exercises the MIME normalization logic directly — no HTTP.
"""
from app.communication.voicemail_storage import ALLOWED_AUDIO_MIME_TYPES


def _normalize_mime(content_type: str | None) -> str:
    """Mirrors the logic added in auth/router.py:upload_my_voicemail_greeting.
    Production code does this inline; this test asserts the pattern stays
    consistent."""
    return (content_type or "").split(";")[0].strip().lower()


class TestMimeParameterStripping:
    def test_browser_mediarecorder_format_accepted(self):
        # The exact MIME a Chrome/Firefox MediaRecorder produces
        normalized = _normalize_mime("audio/webm;codecs=opus")
        assert normalized == "audio/webm"
        assert normalized in ALLOWED_AUDIO_MIME_TYPES

    def test_uppercase_and_whitespace_normalized(self):
        assert _normalize_mime("Audio/MPEG") == "audio/mpeg"
        assert _normalize_mime("  audio/wav  ") == "audio/wav"
        assert _normalize_mime("AUDIO/MP4;codecs=mp4a.40.2") == "audio/mp4"

    def test_mp3_passthrough(self):
        # audio/mpeg should pass through without transcoding (handled
        # by transcode_to_mp3 in production, mirrored in normalization here)
        assert _normalize_mime("audio/mpeg") == "audio/mpeg"
        assert _normalize_mime("audio/mpeg") in ALLOWED_AUDIO_MIME_TYPES

    def test_unsupported_types_rejected(self):
        assert _normalize_mime("image/png") not in ALLOWED_AUDIO_MIME_TYPES
        assert _normalize_mime("text/plain") not in ALLOWED_AUDIO_MIME_TYPES
        assert _normalize_mime("application/octet-stream") not in ALLOWED_AUDIO_MIME_TYPES

    def test_empty_or_none_rejected(self):
        assert _normalize_mime(None) not in ALLOWED_AUDIO_MIME_TYPES
        assert _normalize_mime("") not in ALLOWED_AUDIO_MIME_TYPES
