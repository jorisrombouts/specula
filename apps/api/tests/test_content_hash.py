from specula_api.pipeline.content_hash import content_hash, normalize_url


def test_normalize_url_lowercases_host() -> None:
    assert normalize_url("https://ACME.example.com/jobs/1") == "https://acme.example.com/jobs/1"


def test_normalize_url_drops_fragment() -> None:
    assert normalize_url("https://acme.example.com/jobs/1#apply") == (
        "https://acme.example.com/jobs/1"
    )


def test_normalize_url_strips_tracking_params() -> None:
    url = "https://acme.example.com/jobs/1?utm_source=li&utm_campaign=x&gh_src=abc&ref=xyz"
    assert normalize_url(url) == "https://acme.example.com/jobs/1"


def test_normalize_url_keeps_meaningful_query() -> None:
    url = "https://acme.example.com/jobs?dept=eng&utm_source=li"
    assert normalize_url(url) == "https://acme.example.com/jobs?dept=eng"


def test_normalize_url_sorts_query_for_determinism() -> None:
    a = normalize_url("https://acme.example.com/jobs?b=2&a=1")
    b = normalize_url("https://acme.example.com/jobs?a=1&b=2")
    assert a == b


def test_normalize_url_strips_trailing_slash() -> None:
    assert normalize_url("https://acme.example.com/jobs/1/") == (
        normalize_url("https://acme.example.com/jobs/1")
    )


def test_normalize_url_is_deterministic() -> None:
    url = "https://Acme.example.com/jobs/1?utm_source=li#apply"
    assert normalize_url(url) == normalize_url(url)


def test_content_hash_is_deterministic() -> None:
    kwargs = {
        "source_url": "https://acme.example.com/jobs/1",
        "external_id": "1",
        "title_hint": "Engineer",
    }
    assert content_hash(**kwargs) == content_hash(**kwargs)


def test_content_hash_prefers_external_id_over_url_changes() -> None:
    a = content_hash(
        source_url="https://acme.example.com/jobs/1", external_id="42", title_hint="Engineer"
    )
    b = content_hash(
        source_url="https://acme.example.com/jobs/1?utm_source=li",
        external_id="42",
        title_hint="Engineer (updated)",
    )
    assert a == b


def test_content_hash_falls_back_to_url_and_title_without_external_id() -> None:
    a = content_hash(
        source_url="https://acme.example.com/jobs/1", external_id=None, title_hint="Engineer"
    )
    b = content_hash(
        source_url="https://acme.example.com/jobs/1", external_id=None, title_hint="Engineer"
    )
    c = content_hash(
        source_url="https://acme.example.com/jobs/1", external_id=None, title_hint="Other"
    )
    assert a == b
    assert a != c


def test_content_hash_scoped_by_host_for_same_external_id() -> None:
    # Different ATS hosts issuing the same external_id must not collide.
    a = content_hash(
        source_url="https://boards.greenhouse.io/acme/jobs/1", external_id="1", title_hint=None
    )
    b = content_hash(source_url="https://jobs.lever.co/other/1", external_id="1", title_hint=None)
    assert a != b


def test_content_hash_is_hex_sha256() -> None:
    result = content_hash(
        source_url="https://acme.example.com/jobs/1", external_id="1", title_hint=None
    )
    assert len(result) == 64
    int(result, 16)  # raises ValueError if not hex
