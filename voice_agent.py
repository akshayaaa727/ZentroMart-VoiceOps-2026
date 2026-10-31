
import os
import re

from dotenv import load_dotenv
from gnani.stt.client import GnaniSTTClient
from gnani.tts.client import GnaniTTSClient

from answer import (
    load_documents,
    generate_answer,
    is_ticket_request,
    extract_order_id,
)
from tools.tools import lookup_order, create_ticket


load_dotenv()

stt = GnaniSTTClient()
tts = GnaniTTSClient(api_key=os.getenv("GNANI_API_KEY"))


def make_speech_friendly(text):
    """Remove URLs and source citations before sending text to TTS."""
    text = re.sub(
        r"\(Source:.*?\)",
        "",
        text,
        flags=re.I | re.S,
    )
    text = re.sub(
        r"\[Source:.*?(?:\]\)|\]\])",
        "",
        text,
        flags=re.I | re.S,
    )
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class VoiceAgent:

    def __init__(self):
        self.documents = load_documents()
        self.last_issue = ""
        self.pending_order = None
        self.last_evidence = []

    def respond(self, question):
        question = question.strip()
        self.last_evidence = []

        if not question:
            return "Sorry, I didn't catch that. Could you repeat?"

        # 1. Handle ticket requests.
        if is_ticket_request(question):

            if len(self.last_issue) < 20:
                return (
                    "Please describe your issue in more detail "
                    "before I create a ticket."
                )

            result = create_ticket(
                summary=(
                    f"Customer issue: {self.last_issue}. "
                    "Customer requested human support."
                ),
                order_id=extract_order_id(self.last_issue),
                reason="Customer requested escalation",
                intent="human_escalation",
            )

            if result.get("created") is True:
                self.last_issue = ""
                return (
                    "Your support ticket has been created. "
                    f"Your ticket ID is {result['ticket_id']}."
                )

            return "I couldn't create your ticket. Please try again."

        # 2. Verify an order before disclosing details.
        if self.pending_order:

            result = lookup_order(
                self.pending_order,
                verification_value=question,
            )

            self.pending_order = None

            if (
                result.get("verified") is True
                and result.get("found") is True
            ):
                fields = [
                    f"{key.replace('_', ' ').title()}: {result[key]}"
                    for key in (
                        "status",
                        "order_status",
                        "payment_status",
                        "delivery_date",
                        "expected_delivery_date",
                    )
                    if result.get(key) is not None
                ]

                self.last_issue = ""

                if fields:
                    return (
                        "Your identity is verified. "
                        + ". ".join(fields)
                    )

                return "Your identity is verified, but no order details are available."

            return (
                "I couldn't verify your details. "
                "For your privacy, I cannot disclose order information."
            )

        # 3. Start an order lookup.
        order_id = extract_order_id(question)

        if order_id:
            result = lookup_order(order_id)

            if result.get("verification_required") is True:
                self.pending_order = order_id
                self.last_issue = question

                return (
                    f"Before I can look up order {order_id}, "
                    "please provide the last four digits of your "
                    "registered phone number or your delivery pincode."
                )

            return "I couldn't start the order verification process."

        # 4. Answer general questions using RAG.
        self.last_issue = question

        answer, evidence = generate_answer(
            question,
            self.documents,
        )

        self.last_evidence = evidence

        return answer


def voice_turn(audio_path, agent, output_file="reply.wav"):
    """Convert customer audio into a spoken support response."""

    transcription = stt.transcribe(
        audio_path,
        language_code="en-IN",
    )

    heard = transcription.get("transcript", "").strip()

    reply = agent.respond(heard)

    spoken_reply = make_speech_friendly(reply)

    tts.synthesize(
        spoken_reply,
        voice="Kaveri",
        model="timbre-v2.5",
        language="en-IN",
        output_file=output_file,
    )

    return heard, reply

