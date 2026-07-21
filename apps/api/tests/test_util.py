import pytest

from specula_api.pipeline.util import html_to_text, title_matches_roles, to_country_code

# --- title_matches_roles ---------------------------------------------------------


def test_title_matches_roles_true_when_title_contains_a_role_case_insensitively() -> None:
    assert title_matches_roles("Senior DATA SCIENTIST II", ["Data Scientist", "ML Engineer"])


def test_title_matches_roles_false_when_no_role_title_is_a_substring() -> None:
    assert not title_matches_roles(
        "Enterprise Account Executive - DACH", ["Data Scientist", "ML Engineer"]
    )


def test_title_matches_roles_true_when_title_is_none() -> None:
    # Some ATS/generic-HTML adapters can't produce a feed title — can't filter on nothing.
    assert title_matches_roles(None, ["Data Scientist"])


def test_title_matches_roles_true_when_no_role_titles_given() -> None:
    # No profile/targeting on record — nothing to filter against, so keep it.
    assert title_matches_roles("Account Executive", [])


# --- html_to_text -----------------------------------------------------------------


def test_html_to_text_strips_script_style_noscript_and_svg() -> None:
    html = (
        "<html><body>"
        "<script>track('evil');</script>"
        "<style>.h{color:red}</style>"
        "<noscript>enable JS</noscript>"
        "<svg><path d='M0 0'/></svg>"
        "<h1>Senior Backend Engineer</h1>"
        "<p>Join our team.</p>"
        "</body></html>"
    )

    result = html_to_text(html)

    assert result == "Senior Backend Engineer Join our team."
    assert "track" not in result
    assert "color:red" not in result
    assert "enable JS" not in result
    assert "M0 0" not in result


def test_html_to_text_collapses_whitespace_between_and_within_tags() -> None:
    html = (
        "<html><body>\n  <h1>Title\twith\ttabs</h1>\n\n"
        "  <p>Line one.\n  Line two.</p>\n</body></html>"
    )

    result = html_to_text(html)

    assert result == "Title with tabs Line one. Line two."
    assert "  " not in result  # no double spaces survive collapse
    assert "\n" not in result
    assert "\t" not in result


def test_html_to_text_truncates_to_max_chars() -> None:
    html = "<html><body>" + ("word " * 100) + "</body></html>"

    result = html_to_text(html, max_chars=20)

    assert len(result) == 20
    assert result == ("word " * 100).strip()[:20]


# --- to_country_code --------------------------------------------------------------


def test_to_country_code_passes_alpha2_through_uppercased() -> None:
    assert to_country_code("ES") == "ES"
    assert to_country_code("es") == "ES"
    assert to_country_code("gb") == "GB"


def test_to_country_code_resolves_full_names() -> None:
    assert to_country_code("Spain") == "ES"
    assert to_country_code("United Kingdom") == "GB"
    assert to_country_code("Netherlands") == "NL"
    assert to_country_code("Czechia") == "CZ"
    assert to_country_code("Czech Republic") == "CZ"
    assert to_country_code("United States") == "US"


def test_to_country_code_resolves_common_variants() -> None:
    assert to_country_code("UK") == "GB"
    assert to_country_code("USA") == "US"


@pytest.mark.parametrize(
    "word",
    ["Global", "Remote", "Worldwide", "EMEA", "EU", "Europe", "Anywhere", "LATAM", "APAC"],
)
def test_to_country_code_rejects_non_country_words(word: str) -> None:
    assert to_country_code(word) is None


def test_to_country_code_none_and_blank_are_none() -> None:
    assert to_country_code(None) is None
    assert to_country_code("") is None
    assert to_country_code("   ") is None


def test_to_country_code_unknown_gibberish_is_none_never_a_wrong_code() -> None:
    assert to_country_code("Qwxzplorf Nonexistica") is None
