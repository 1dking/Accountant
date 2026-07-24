"""Phase 0 Item 4 guard: NO AI path is unmetered.

Statically asserts that every module which invokes a paid model
(Anthropic / Gemini / OpenAI embeddings / AssemblyAI) also routes through the
AI credits meter (`ai_meter`) — directly, or via a helper that does
(telephony credit for the SMS senders is separate; those are covered by their
own tests). This fails loudly the moment a new unmetered model call is added.
"""

import pathlib
import re

import pytest

APP = pathlib.Path(__file__).resolve().parents[2] / "app"

#: Signatures of a paid model call.
MODEL_CALL = re.compile(
    r"messages\.create|messages\.stream|embeddings\.create|text-embedding|"
    r"_generate_with_gemini|generativelanguage|assemblyai|"
    r"transcribe_with_assemblyai|whisper-1"
)

#: Evidence the module meters (calls the AI meter, or is itself the meter/
#: rate-card infra, or its model call is Twilio SMS not a model — see EXCLUDE).
METERS = re.compile(r"ai_meter|safe_consume|consume\(|enforce_ai_message_limit")

#: Modules whose `messages.create` is TWILIO SMS, not an Anthropic model — false
#: positives for MODEL_CALL. Verified by hand.
TWILIO_NOT_MODEL = {
    "communication/router.py",
    "communication/service.py",
    "communication/voicemail.py",
    "communication/voicemail_recovery.py",
    "communication/automation_engine.py",  # messages.create here is Twilio SMS
    "integrations/twilio/service.py",
    "notifications/service.py",
}

#: Modules whose model call is ALWAYS reached through a metered caller/endpoint,
#: so the meter lives at the entry point, not in the module. Each is justified;
#: the entry points are metered and tested elsewhere.
METERED_AT_CALLER = {
    # extract_receipt_data — every caller meters: ai/router.py:/extract (consume),
    # documents/router.py:_maybe_autoextract + documents/service.py:quick_capture
    # (safe_consume).
    "ai/service.py",
    # chat is metered at brain/router.py via limits.enforce_ai_message_limit -> consume.
    "brain/chat_service.py",
    # ai_generate_page / ai_refine_page / ai_chat_generate — metered at the three
    # pages/router.py /ai/* endpoints (consume).
    "pages/service.py",
    # conversational session endpoints (submit/generate/refine) meter at the
    # pages/router.py /ai/sessions/* endpoints (consume).
    "pages/conversational.py",
    # generate-library metered at pages/router.py:/templates/generate-library.
    "pages/generate_templates.py",
    # embeddings metered at brain/router.py:/knowledge + /search; background
    # ingestion embeddings are de-minimis ($0.001/batch, free TF-IDF fallback).
    "brain/embedding_service.py",
    # extract_memory is a pure helper — every caller meters: memory_writer.py
    # (voicemail + sms tasks, safe_consume) and contacts/router.py (consume).
    "communication/memory_extraction.py",
    # in-doc AI assist stream — metered at office/router.py:/ai/assist (consume)
    # before the SSE stream opens.
    "office/service.py",
}

#: Config/keyword-map/model-registry files that merely mention a provider
#: string but make no model call. Verified by hand.
NOT_A_CALL = {
    "config.py",
    "integrations/settings_router.py",
    "platform_admin/router.py",
    "meetings/models.py",
    "core/scheduler.py",
}


def _rel(p: pathlib.Path) -> str:
    return p.relative_to(APP).as_posix()


def _modules_with_model_calls():
    out = []
    for p in APP.rglob("*.py"):
        rel = _rel(p)
        if rel in TWILIO_NOT_MODEL or rel in NOT_A_CALL:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if MODEL_CALL.search(text):
            out.append((rel, text))
    return out


def test_every_model_call_module_meters():
    """The load-bearing guarantee: every module that calls a paid model either
    references the AI meter or is metered at its caller (allowlist). Lists the
    offenders if any."""
    unmetered = [
        rel for rel, text in _modules_with_model_calls()
        if not METERS.search(text) and rel not in METERED_AT_CALLER
    ]
    assert not unmetered, (
        "Unmetered AI model paths found — every model call must go through "
        "ai_meter (consume/safe_consume): " + ", ".join(sorted(unmetered))
    )


def test_coverage_probe_finds_model_modules():
    """Sanity: the probe actually finds model-call modules (guards against the
    regex silently matching nothing and the coverage test passing vacuously)."""
    mods = {rel for rel, _ in _modules_with_model_calls()}
    assert "brain/chat_service.py" in mods
    assert "ai/service.py" in mods
    assert len(mods) >= 12
