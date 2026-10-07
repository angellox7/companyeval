from django.test import SimpleTestCase

from evaluations.constants import FACTORS
from evaluations.scoring import (
    band_position,
    floor_position,
    score_factors,
    screen_label_for,
)


DEFAULT_WEIGHTS = {
    "team": 30,
    "market": 25,
    "product": 20,
    "traction": 15,
    "terms": 10,
}


def _all(score):
    return {key: score for factors in FACTORS.values() for key, _label in factors}


def _category(category, score):
    return {key: score for key, _label in FACTORS[category]}


class ScreenLabelTests(SimpleTestCase):
    def test_boundaries(self):
        self.assertEqual(screen_label_for(75), "Strong pursue")
        self.assertEqual(screen_label_for(100), "Strong pursue")
        self.assertEqual(screen_label_for(74.9), "Worth a deeper look")
        self.assertEqual(screen_label_for(60), "Worth a deeper look")
        self.assertEqual(screen_label_for(59.9), "Mixed")
        self.assertEqual(screen_label_for(45), "Mixed")
        self.assertEqual(screen_label_for(44.9), "Lean pass")
        self.assertEqual(screen_label_for(0), "Lean pass")


class BandPositionTests(SimpleTestCase):
    def test_band(self):
        self.assertEqual(band_position(7, 8, 15), "below")
        self.assertEqual(band_position(8, 8, 15), "in_band")
        self.assertEqual(band_position(15, 8, 15), "in_band")
        self.assertEqual(band_position(16, 8, 15), "above")
        self.assertIsNone(band_position(None, 8, 15))

    def test_floor(self):
        self.assertEqual(floor_position(999, 1000), "below")
        self.assertEqual(floor_position(1000, 1000), "in_band")
        self.assertIsNone(floor_position(None, 1000))


class ScoreFactorTests(SimpleTestCase):
    def test_unscored_deal_has_no_composite(self):
        evaluation = score_factors({}, DEFAULT_WEIGHTS)
        self.assertIsNone(evaluation.composite)
        self.assertFalse(evaluation.complete)
        self.assertEqual(evaluation.scored_count, 0)
        self.assertEqual(evaluation.factor_count, 14)
        self.assertEqual(evaluation.screen_label, "")

    def test_all_threes_meet_the_bar(self):
        evaluation = score_factors(_all(3), DEFAULT_WEIGHTS)
        self.assertEqual(evaluation.composite, 60)
        self.assertTrue(evaluation.complete)
        self.assertEqual(evaluation.composite_display, "60")
        self.assertEqual(evaluation.screen_label, "Worth a deeper look")

    def test_all_fives_and_ones(self):
        top = score_factors(_all(5), DEFAULT_WEIGHTS)
        bottom = score_factors(_all(1), DEFAULT_WEIGHTS)
        self.assertEqual(top.composite, 100)
        self.assertEqual(top.screen_label, "Strong pursue")
        self.assertEqual(bottom.composite, 20)
        self.assertEqual(bottom.screen_label, "Lean pass")

    def test_all_fours_are_a_strong_pursue(self):
        evaluation = score_factors(_all(4), DEFAULT_WEIGHTS)
        self.assertEqual(evaluation.composite, 80)
        self.assertEqual(evaluation.screen_label, "Strong pursue")

    def test_partial_factor_counts_as_its_share_of_the_category(self):
        evaluation = score_factors({"domain_expertise": 5}, DEFAULT_WEIGHTS)
        team = evaluation.categories[0]
        self.assertEqual(team.points, 10)
        self.assertEqual(team.running_average, 5)
        self.assertFalse(team.complete)
        self.assertEqual(evaluation.composite, 10)
        self.assertTrue(evaluation.partial)
        self.assertEqual(evaluation.screen_label, "")
        self.assertEqual(evaluation.scored_count, 1)

    def test_finished_team_only_stays_partial(self):
        evaluation = score_factors(_category("team", 5), DEFAULT_WEIGHTS)
        self.assertEqual(evaluation.categories[0].points, 30)
        self.assertEqual(evaluation.composite, 30)
        self.assertFalse(evaluation.complete)
        self.assertEqual(evaluation.screen_label, "")

    def test_weights_change_a_complete_score(self):
        scores = {}
        scores.update(_category("team", 5))
        scores.update(_category("market", 1))
        scores.update(_category("product", 1))
        scores.update(_category("traction", 1))
        scores.update(_category("terms", 1))

        default = score_factors(scores, DEFAULT_WEIGHTS)
        self.assertEqual(default.composite, 44)
        self.assertEqual(default.screen_label, "Lean pass")

        custom = score_factors(
            scores,
            {"team": 50, "market": 20, "product": 10, "traction": 10, "terms": 10},
        )
        self.assertEqual(custom.composite, 60)
        self.assertEqual(custom.screen_label, "Worth a deeper look")

    def test_mixed_complete_score_is_mixed(self):
        scores = {}
        scores.update(_category("team", 5))
        scores.update(_category("market", 3))
        scores.update(_category("product", 1))
        scores.update(_category("traction", 1))
        scores.update(_category("terms", 1))
        evaluation = score_factors(scores, DEFAULT_WEIGHTS)
        self.assertEqual(evaluation.composite, 54)
        self.assertEqual(evaluation.screen_label, "Mixed")
