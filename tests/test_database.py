"""اختبارات طبقة البيانات بعميل وهمي، بلا اتصال خارجي."""

from datetime import date
from types import SimpleNamespace

import pytest

from database import Database


class Query:
    def __init__(self, data):
        self.data = data

    def select(self, *_args, **_kwargs): return self
    def order(self, *_args, **_kwargs): return self
    def eq(self, key, value):
        self.data = [row for row in self.data if row.get(key) == value]
        return self
    def limit(self, number):
        self.data = self.data[:number]
        return self
    def execute(self): return SimpleNamespace(data=self.data, count=len(self.data))


class FakeClient:
    def __init__(self, rows): self.rows = rows
    def table(self, _name): return Query(list(self.rows))


def test_search_diseases_handles_arabic_and_english():
    rows = [
        {"id": "1", "name_ar": "مرض اصطناعي", "name_en": "Synthetic Disease", "week_number": 1},
        {"id": "2", "name_ar": "حالة تجريبية", "name_en": "Test Condition", "week_number": 2},
    ]
    database = Database(client=FakeClient(rows))
    assert database.search_diseases("اصطناعي")[0]["id"] == "1"
    assert database.search_diseases("test")[0]["id"] == "2"
    assert database.search_diseases("") == []


class DuplicateKeyError(Exception):
    code = "23505"


class PublicationQuery:
    def __init__(self, client):
        self.client = client

    def insert(self, payload):
        self.client.inserted = payload
        raise DuplicateKeyError("duplicate key")

    def update(self, payload):
        self.client.updated = payload
        return self

    def eq(self, key, value):
        self.client.filters.append((key, value))
        return self

    def lt(self, key, value):
        self.client.filters.append((key, value))
        return self

    def execute(self):
        return SimpleNamespace(data=self.client.reclaimed_rows)


class PublicationClient:
    def __init__(self, reclaimed_rows):
        self.reclaimed_rows = reclaimed_rows
        self.filters = []
        self.inserted = None
        self.updated = None

    def table(self, name):
        assert name == "daily_publications"
        return PublicationQuery(self)


@pytest.mark.parametrize("reclaimed_rows, expected", [([{"publication_date": "2026-01-01"}], True), ([], False)])
def test_claim_daily_publication_reclaims_only_expired_in_progress_lease(reclaimed_rows, expected):
    client = PublicationClient(reclaimed_rows)
    database = Database(client=client)

    assert database.claim_daily_publication(date(2026, 1, 1), "disease-id") is expected
    assert client.inserted["status"] == "in_progress"
    assert "lease_expires_at" in client.inserted
    assert client.updated is not None
    assert ("status", "in_progress") in client.filters
    assert any(key == "lease_expires_at" for key, _value in client.filters)
