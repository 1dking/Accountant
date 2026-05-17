"""SMS automation flow engine.

User-defined multi-step SMS sequences triggered on call events. Each step
has a message body (literal text — NO AI generation) and a delay-before-send.

Triggered fire-and-forget after a missed call or voicemail. Idempotency
guard on call_logs.automation_flow_triggered_at: each call fires its flow
exactly once.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.auth.models import User
from app.communication.models import (
    CallLog,
    SmsAutomationFlow,
    SmsAutomationStep,
    SmsMessage,
    TwilioPhoneNumber,
)

logger = logging.getLogger(__name__)


async def _get_active_flow(
    db, user_id: uuid.UUID, trigger_type: str
) -> SmsAutomationFlow | None:
    """First active flow for this (user, trigger_type) pair. Users could
    in principle have multiple flows for the same trigger — we take the
    first by created_at to be deterministic."""
    result = await db.execute(
        select(SmsAutomationFlow)
        .where(
            SmsAutomationFlow.user_id == user_id,
            SmsAutomationFlow.trigger_type == trigger_type,
            SmsAutomationFlow.is_active == True,  # noqa: E712
        )
        .order_by(SmsAutomationFlow.created_at)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_flow_steps(db, flow_id: uuid.UUID) -> list[SmsAutomationStep]:
    result = await db.execute(
        select(SmsAutomationStep)
        .where(SmsAutomationStep.flow_id == flow_id)
        .order_by(SmsAutomationStep.step_order)
    )
    return list(result.scalars().all())


def _render_message(
    step: SmsAutomationStep, user_booking_link: str | None
) -> str:
    """Render the final SMS body. Currently: append booking link if both
    the step opts in AND the user has one configured."""
    body = step.message_body or ""
    if step.include_booking_link and user_booking_link:
        body = f"{body}\n\n{user_booking_link}" if body else user_booking_link
    return body[:1600]  # Twilio absolute max — segmentation handled by carrier


async def trigger_flow_for_call(
    call_log_id: uuid.UUID,
    trigger_type: str,
    session_factory,
) -> None:
    """Fire-and-forget: look up the user's active flow for trigger_type
    and execute its steps. Idempotent via call_logs.automation_flow_triggered_at.
    """
    logger.info(
        "automation_flow.fired call_log_id=%s trigger=%s",
        call_log_id, trigger_type,
    )

    try:
        # Phase 1: snapshot user + flow + steps under our own session,
        # then claim the idempotency slot.
        async with session_factory() as db:
            row = await db.execute(select(CallLog).where(CallLog.id == call_log_id))
            call_log = row.scalar_one_or_none()
            if call_log is None:
                logger.warning(
                    "automation_flow.skipped row_gone call_log_id=%s", call_log_id
                )
                return
            if call_log.automation_flow_triggered_at is not None:
                logger.info(
                    "automation_flow.skipped_already_fired call_log_id=%s "
                    "fired_at=%s",
                    call_log_id, call_log.automation_flow_triggered_at,
                )
                return
            if call_log.user_id is None:
                logger.info(
                    "automation_flow.skipped_no_user call_log_id=%s", call_log_id
                )
                return

            flow = await _get_active_flow(db, call_log.user_id, trigger_type)
            if flow is None:
                logger.info(
                    "automation_flow.skipped_no_flow call_log_id=%s "
                    "user_id=%s trigger=%s",
                    call_log_id, call_log.user_id, trigger_type,
                )
                return

            steps = await _get_flow_steps(db, flow.id)
            if not steps:
                logger.info(
                    "automation_flow.skipped_no_steps call_log_id=%s flow_id=%s",
                    call_log_id, flow.id,
                )
                return

            # Snapshot the values we need (DB session closes after this block)
            user_row = await db.execute(
                select(User).where(User.id == call_log.user_id)
            )
            user = user_row.scalar_one_or_none()
            if user is None:
                logger.warning(
                    "automation_flow.skipped_user_gone call_log_id=%s", call_log_id
                )
                return

            phone_row = await db.execute(
                select(TwilioPhoneNumber).where(
                    TwilioPhoneNumber.assigned_user_id == user.id
                )
            )
            phone = phone_row.scalar_one_or_none()
            if phone is None:
                logger.warning(
                    "automation_flow.skipped_no_assigned_number call_log_id=%s "
                    "user_id=%s",
                    call_log_id, user.id,
                )
                return

            # Claim the idempotency slot now — even if the loop fails partway,
            # we don't want a second trigger to re-fire all steps.
            call_log.automation_flow_triggered_at = datetime.now(timezone.utc)
            await db.commit()

            flow_id = flow.id
            user_id = user.id
            user_booking_link = user.booking_link
            from_number = phone.phone_number
            to_number = call_log.from_number
            contact_id = call_log.contact_id
            snapshotted_steps = [
                {
                    "step_order": s.step_order,
                    "message_body": s.message_body,
                    "delay_minutes": s.delay_minutes,
                    "include_booking_link": s.include_booking_link,
                }
                for s in steps
            ]

        # Phase 2: execute each step with its delay. Re-check is_active
        # before each send so a user can stop the sequence mid-flight.
        from app.config import Settings
        settings = Settings()
        if not settings.twilio_account_sid or not settings.twilio_auth_token:
            logger.warning(
                "automation_flow.twilio_not_configured call_log_id=%s", call_log_id
            )
            return

        from twilio.rest import Client
        twilio_client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

        for step_data in snapshotted_steps:
            if step_data["delay_minutes"] > 0:
                await asyncio.sleep(step_data["delay_minutes"] * 60)

            # Re-check is_active under a fresh session
            async with session_factory() as db:
                flow_row = await db.execute(
                    select(SmsAutomationFlow).where(SmsAutomationFlow.id == flow_id)
                )
                current_flow = flow_row.scalar_one_or_none()
                if current_flow is None or not current_flow.is_active:
                    logger.info(
                        "automation_flow.aborted_inactive call_log_id=%s "
                        "flow_id=%s step_order=%s",
                        call_log_id, flow_id, step_data["step_order"],
                    )
                    return

            # Build a synthetic step object for rendering
            synth = SmsAutomationStep(
                message_body=step_data["message_body"],
                include_booking_link=step_data["include_booking_link"],
            )
            body = _render_message(synth, user_booking_link)

            try:
                twilio_msg = twilio_client.messages.create(
                    body=body, from_=from_number, to=to_number,
                )
                send_status = "sent"
                sid = twilio_msg.sid
            except Exception as e:
                logger.error(
                    "automation_flow.step_send_failed call_log_id=%s "
                    "step_order=%s error=%s",
                    call_log_id, step_data["step_order"], str(e)[:200],
                )
                send_status = "failed"
                sid = None

            # Persist as outbound SMS for thread visibility
            async with session_factory() as db:
                sms = SmsMessage(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    contact_id=contact_id,
                    direction="outbound",
                    from_number=from_number,
                    to_number=to_number,
                    body=body[:1600],
                    status=send_status,
                    twilio_sid=sid,
                )
                db.add(sms)
                await db.commit()

            logger.info(
                "automation_flow.step_sent call_log_id=%s step_order=%s status=%s",
                call_log_id, step_data["step_order"], send_status,
            )

        logger.info(
            "automation_flow.completed call_log_id=%s steps=%d",
            call_log_id, len(snapshotted_steps),
        )
    except Exception as e:
        logger.error(
            "automation_flow.task_failure call_log_id=%s error=%s",
            call_log_id, str(e)[:300], exc_info=True,
        )
