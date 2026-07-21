import pytest

from specula_api.pipeline.util import (
    html_to_text,
    title_matches_roles,
    to_country_code,
    to_skill_tokens,
)

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


# --- to_skill_tokens -------------------------------------------------------------
#
# Real strings observed in the live corpus: 11% of extracted "skills" were requirement
# SENTENCES rather than skill names. A sentence embeds nowhere near a skill token, so it
# can never match a candidate skill — it just inflates overlap_total and deflates
# factor_skill, the same systematic understatement semantic matching was meant to end.


def test_to_skill_tokens_keeps_skill_names() -> None:
    assert to_skill_tokens(["Python", "PyTorch", "scikit-learn"]) == [
        "Python",
        "PyTorch",
        "scikit-learn",
    ]


def test_to_skill_tokens_keeps_short_multiword_skills() -> None:
    # Genuine skills are often 2-4 words — the cap must not eat them.
    assert to_skill_tokens(
        ["Natural Language Processing", "A/B testing", "PyTorch Distributed"]
    ) == [
        "Natural Language Processing",
        "A/B testing",
        "PyTorch Distributed",
    ]


def test_to_skill_tokens_cap_is_exactly_six_words() -> None:
    """Pins the cap's VALUE, not just its neighbourhood.

    Without this, the longest kept string in the suite is 3 words and the shortest dropped
    is 8 — so every cap from 3 to 7 passes, and the tests say nothing about which one is
    actually configured. Six is the corpus boundary: 88% of real skills were <= 6 words and
    everything longer was a sentence.
    """
    six = "Extract Transform Load Pipeline Design Work"
    seven = f"{six} Here"
    assert len(six.split()) == 6
    assert len(seven.split()) == 7

    assert to_skill_tokens([six]) == [six], "6 words is at the cap and must be KEPT"
    assert to_skill_tokens([seven]) == [], "7 words is over the cap and must be DROPPED"


def test_to_skill_tokens_drops_requirement_sentences() -> None:
    # Verbatim from the live corpus.
    assert to_skill_tokens(
        [
            "Python",
            "8+ years of experience in software engineering, machine learning engineering, "
            "or applied AI",
            "SQL",
        ]
    ) == ["Python", "SQL"]


def test_to_skill_tokens_drops_a_sentence_that_names_real_skills() -> None:
    # Tempting to keep because it mentions PyTorch — but as one string it matches nothing
    # and only inflates the denominator. Decomposing it is the model's job (prompt), not a
    # regex's.
    assert (
        to_skill_tokens(
            [
                "Hands-on experience with Megatron-LM/Megatron-Core/NeMo, DeepSpeed, or "
                "serious FSDP/ZeRO expertise"
            ]
        )
        == []
    )


def test_to_skill_tokens_strips_whitespace_and_drops_blanks() -> None:
    assert to_skill_tokens(["  Python  ", "", "   ", "SQL"]) == ["Python", "SQL"]


def test_to_skill_tokens_empty_list_stays_empty() -> None:
    assert to_skill_tokens([]) == []


def test_to_skill_tokens_preserves_order() -> None:
    assert to_skill_tokens(["SQL", "Python", "Docker"]) == ["SQL", "Python", "Docker"]
