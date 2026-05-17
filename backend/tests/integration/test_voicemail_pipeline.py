"""Bug #1 regression: statusCallback must be on <Number>/<Client>, not <Dial>.

Symptom (2026-05-16): voice call-status webhook never fired even though
the handler was wired correctly. Root cause: Twilio silently ignores
statusCallback when set on <Dial>; it must be on the dialed noun
(<Number> or <Client>).

This test renders the TwiML output (no HTTP, no DB) and asserts the
attribute placement via XML parsing — not string matching. Pre-fix
this test would have failed; post-fix it passes.
"""
import xml.etree.ElementTree as ET

from twilio.twiml.voice_response import VoiceResponse, Dial


def render_outbound_twiml() -> str:
    """Mirror the shape of voice_twiml outbound (caller dials user)."""
    response = VoiceResponse()
    response.say("This call may be recorded.", voice="Polly.Joanna")
    dial = Dial(
        record="record-from-answer-dual",
        recording_status_callback="https://accountant.ocidm.io/recording-status",
        recording_status_callback_method="POST",
        caller_id="+13659092096",
    )
    dial.number(
        "+15555550199",
        status_callback="https://accountant.ocidm.io/call-status",
        status_callback_method="POST",
        status_callback_event="initiated ringing answered completed",
    )
    response.append(dial)
    return str(response)


def render_inbound_twiml() -> str:
    """Mirror voice_incoming (caller → user's browser <Client>)."""
    response = VoiceResponse()
    dial = Dial(
        timeout=10,
        action="https://accountant.ocidm.io/incoming-fallback",
        record="record-from-answer-dual",
        recording_status_callback="https://accountant.ocidm.io/recording-status",
        recording_status_callback_method="POST",
    )
    dial.client(
        "abc-user-uuid",
        status_callback="https://accountant.ocidm.io/call-status",
        status_callback_method="POST",
        status_callback_event="initiated ringing answered completed",
    )
    response.append(dial)
    return str(response)


class TestVoiceStatusCallbackPlacement:
    def test_outbound_statuscallback_on_number_not_dial(self):
        xml = render_outbound_twiml()
        root = ET.fromstring(xml)
        dial = root.find("Dial")
        assert dial is not None, "missing <Dial>"

        # statusCallback MUST be on the nested <Number>, NOT on <Dial>
        assert "statusCallback" not in dial.attrib, (
            f"statusCallback wrongly set on <Dial>: {dial.attrib}"
        )
        number = dial.find("Number")
        assert number is not None, "missing <Number> inside <Dial>"
        assert "statusCallback" in number.attrib
        assert "statusCallbackEvent" in number.attrib
        assert "statusCallbackMethod" in number.attrib

        # recordingStatusCallback DOES belong on <Dial> (bridge-scoped)
        assert "recordingStatusCallback" in dial.attrib

    def test_inbound_statuscallback_on_client_not_dial(self):
        xml = render_inbound_twiml()
        root = ET.fromstring(xml)
        dial = root.find("Dial")
        assert dial is not None
        assert "statusCallback" not in dial.attrib
        client = dial.find("Client")
        assert client is not None
        assert "statusCallback" in client.attrib
        assert "statusCallbackEvent" in client.attrib
