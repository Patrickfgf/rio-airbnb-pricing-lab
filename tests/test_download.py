import src.data.download as dl


class _FakeResp:
    def __init__(self, status, content=b"data"):
        self.status_code = status
        self.content = content

    def iter_content(self, chunk_size):
        yield self.content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_resolve_snapshot_picks_first_200(monkeypatch):
    def fake_head(url, *, headers, timeout):
        return _FakeResp(200 if "2026-03-31" in url else 404)

    monkeypatch.setattr(dl.requests, "head", fake_head)
    date = dl.resolve_snapshot_date(["2026-06-30", "2026-03-31"])
    assert date == "2026-03-31"


def test_resolve_honors_override(monkeypatch):
    monkeypatch.setattr(dl.requests, "head", lambda *a, **k: _FakeResp(200))
    assert dl.resolve_snapshot_date(["2099-01-01"], override="2025-12-20") == "2025-12-20"


def test_download_file_writes_with_browser_headers(monkeypatch, tmp_path):
    seen = {}

    def fake_get(url, *, headers, timeout, stream):
        seen["headers"] = headers
        return _FakeResp(200, content=b"gzipped-bytes")

    monkeypatch.setattr(dl.requests, "get", fake_get)
    dest = tmp_path / "listings.csv.gz"
    dl.download_file("http://x/listings.csv.gz", dest)
    assert dest.read_bytes() == b"gzipped-bytes"
    assert "Mozilla" in seen["headers"]["User-Agent"]
    assert seen["headers"]["Referer"].startswith("https://insideairbnb.com")


def test_build_url_rejects_non_date():
    # SSRF / path-breakout guard: a non-date string must never reach the URL.
    import pytest

    with pytest.raises(ValueError):
        dl.build_url("../../etc/passwd", "listings")


def test_build_url_rejects_unknown_file():
    import pytest

    with pytest.raises(ValueError):
        dl.build_url("2026-03-30", "reviews")  # not in DUMP_FILES for Phase 1
