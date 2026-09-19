"""اختبارات وحدات منطق البوت باستخدام بيانات اصطناعية."""

import asyncio

from telegram.error import TelegramError

from bot import format_disease, format_question, publish_daily_content
from database import DatabaseError


def test_format_disease_escapes_html():
    disease = {
        "name_ar": "مرض <تجريبي>",
        "name_en": "Synthetic",
        "definition": "تعريف",
        "symptoms": "أعراض",
        "treatment": "علاج",
    }
    message = format_disease(disease)
    assert "&lt;تجريبي&gt;" in message
    assert "ليس تشخيصًا" in message


def test_format_question_has_four_callbacks():
    question = {
        "id": "00000000-0000-0000-0000-000000000001",
        "question": "سؤال اصطناعي؟",
        "option_a": "أ",
        "option_b": "ب",
        "option_c": "ج",
        "option_d": "د",
    }
    text, keyboard = format_question(question)
    assert "سؤال اصطناعي" in text
    assert len(keyboard.inline_keyboard) == 4
    assert keyboard.inline_keyboard[2][0].callback_data.endswith("|C")


def test_disease_message_stays_under_telegram_limit_with_html_characters():
    disease = {
        "name_ar": "<" * 1000,
        "name_en": "&" * 1000,
        "definition": '"' * 5000,
        "symptoms": ">" * 5000,
        "treatment": "&" * 7000,
    }
    message = format_disease(disease)
    assert len(message) <= 3900
    assert "<script>" not in message


class PublicationDatabase:
    disease = {
        "id": "00000000-0000-0000-0000-000000000001",
        "name_ar": "مرض اصطناعي",
        "name_en": "Synthetic",
        "definition": "تعريف",
        "symptoms": "أعراض",
        "treatment": "علاج",
    }

    def __init__(self, subscribers):
        self.subscribers = subscribers
        self.released = []
        self.completed = []

    def get_daily_disease(self, _date): return self.disease
    def claim_daily_publication(self, _date, _disease_id): return True
    def list_active_subscribers(self):
        if isinstance(self.subscribers, Exception):
            raise self.subscribers
        return self.subscribers
    def release_daily_publication(self, publication_date, disease_id): self.released.append((publication_date, disease_id))
    def complete_daily_publication(self, publication_date): self.completed.append(publication_date)
    def deactivate_subscriber(self, _user_id): pass


class FailingBot:
    async def send_message(self, **_kwargs):
        raise TelegramError("temporary failure")


def test_publish_releases_claim_if_loading_subscribers_fails():
    database = PublicationDatabase(DatabaseError("unavailable"))

    try:
        asyncio.run(publish_daily_content(FailingBot(), database))
    except DatabaseError:
        pass
    else:
        raise AssertionError("Expected subscriber lookup failure to be propagated")

    assert len(database.released) == 1
    assert not database.completed


def test_publish_releases_claim_and_requests_retry_when_every_delivery_fails():
    database = PublicationDatabase([{"user_id": 42}])

    result = asyncio.run(publish_daily_content(FailingBot(), database))

    assert result == {"published": False, "sent": 0, "failed": 1, "retryable": True}
    assert len(database.released) == 1
    assert not database.completed
