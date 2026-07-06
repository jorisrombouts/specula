from datetime import date, timedelta

from specula_api.services.jobs import derive_loc, is_new, score_match


class TestDeriveLoc:
    def test_base_by_work_mode_for_default_lens(self) -> None:
        assert derive_loc("Remote", "NL", "NL", is_default=True, origin_rule=None) == 92
        assert derive_loc("Hybrid", "NL", "NL", is_default=True, origin_rule=None) == 70
        assert derive_loc("On-site", "NL", "NL", is_default=True, origin_rule=None) == 50

    def test_foreign_hq_lens_rewards_non_local_hq(self) -> None:
        foreign = derive_loc("Remote", "NL", "GB", is_default=False, origin_rule="foreign_hq")
        local = derive_loc("Remote", "NL", "NL", is_default=False, origin_rule="foreign_hq")
        assert foreign > local

    def test_clamped_to_0_100(self) -> None:
        assert 0 <= derive_loc("Remote", "NL", "NL", is_default=True, origin_rule=None) <= 100


class TestScoreMatch:
    def test_weighted_blend_role_skill_loc(self) -> None:
        # 0.4*80 + 0.4*80 + 0.2*90 = 82
        match, red_flag = score_match(80, 80, 90, None)
        assert match == 82
        assert red_flag is None

    def test_low_skill_sets_red_flag_and_caps_at_72(self) -> None:
        match, red_flag = score_match(90, 40, 90, None)
        assert match <= 72
        assert red_flag == "Low required-skill overlap"

    def test_preserves_existing_red_flag(self) -> None:
        _, red_flag = score_match(90, 40, 90, "HQ origin unverified")
        assert red_flag == "HQ origin unverified"


class TestIsNew:
    def test_recent_posting_is_new(self) -> None:
        today = date(2026, 7, 6)
        assert is_new(today - timedelta(days=3), today) is True

    def test_old_posting_is_not_new(self) -> None:
        today = date(2026, 7, 6)
        assert is_new(today - timedelta(days=30), today) is False

    def test_missing_posted_at_is_not_new(self) -> None:
        assert is_new(None, date(2026, 7, 6)) is False
