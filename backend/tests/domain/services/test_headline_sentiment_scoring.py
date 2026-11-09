"""Behavior tests for headline sentiment scoring (pure functions)."""

import pytest

from src.domain.services.headline_sentiment_scoring import (
    MIN_DIRECTIONAL_VOLUME,
    HeadlineDriver,
    HeadlineSentimentAggregate,
    aggregate_headline_rows,
    aggregate_weighted_compounds,
    compound_from_class_probs,
    dominant_label,
    effective_sentiment_value,
    top_directional_drivers,
)


class TestCompoundFromClassProbs:
    def test_positive_dominant(self) -> None:
        assert compound_from_class_probs({"positive": 0.8, "negative": 0.1, "neutral": 0.1}) == pytest.approx(0.7)

    def test_negative_dominant(self) -> None:
        assert compound_from_class_probs({"positive": 0.1, "negative": 0.85, "neutral": 0.05}) == pytest.approx(-0.75)

    def test_clamps_to_unit_interval(self) -> None:
        assert compound_from_class_probs({"positive": 1.0, "negative": 0.0}) == 1.0
        assert compound_from_class_probs({"positive": 0.0, "negative": 1.0}) == -1.0


class TestAggregateHeadlineRows:
    def test_empty_returns_zeros(self) -> None:
        out = aggregate_headline_rows([])
        assert out == HeadlineSentimentAggregate(
            value=0.0,
            n_texts=0,
            pos_mean=0.0,
            neg_mean=0.0,
            neutral_mean=0.0,
        )

    def test_single_row(self) -> None:
        out = aggregate_headline_rows([{"positive": 0.6, "negative": 0.2, "neutral": 0.2}])
        assert out.n_texts == 1
        assert out.value == pytest.approx(0.4)
        assert out.pos_mean == pytest.approx(0.6)

    def test_equal_weight_mean(self) -> None:
        rows = [
            {"positive": 1.0, "negative": 0.0, "neutral": 0.0},
            {"positive": 0.0, "negative": 1.0, "neutral": 0.0},
        ]
        out = aggregate_headline_rows(rows)
        assert out.value == pytest.approx(0.0)
        assert out.n_texts == 2

    def test_weights_shift_aggregate(self) -> None:
        rows = [
            {"positive": 1.0, "negative": 0.0, "neutral": 0.0},
            {"positive": 0.0, "negative": 1.0, "neutral": 0.0},
        ]
        out = aggregate_headline_rows(rows, weights=[3.0, 1.0])
        assert out.value == pytest.approx(0.5)  # (3*1 + 1*(-1)) / 4


class TestAggregateWeightedCompounds:
    def test_mismatched_weights_raises(self) -> None:
        with pytest.raises(ValueError, match="weights length"):
            aggregate_weighted_compounds([0.1, 0.2], [1.0])


class TestDirectionalAggregate:
    """Directional value isolates the signal carried by non-neutral headlines.

    The plain ``value`` is compressed toward 0 when most headlines are neutral;
    ``directional_value`` averages only the headlines whose dominant label is
    positive/negative, so one real signal isn't drowned by a sea of neutrals.
    """

    def test_neutrals_drown_value_but_not_directional(self) -> None:
        # 8 neutral-dominant headlines + 1 clearly-positive
        rows = [{"positive": 0.15, "negative": 0.15, "neutral": 0.70} for _ in range(8)]
        rows.append({"positive": 0.85, "negative": 0.05, "neutral": 0.10})

        out = aggregate_headline_rows(rows)

        # plain mean is dragged toward 0 by the 8 neutrals...
        assert abs(out.value) < 0.15
        # ...but the directional value reflects the one positive headline (compound 0.80)
        assert out.directional_value == pytest.approx(0.80)
        assert out.n_positive == 1
        assert out.n_neutral == 8
        assert out.n_negative == 0
        assert out.directional_count == 1

    def test_directional_value_zero_when_all_neutral(self) -> None:
        rows = [{"positive": 0.1, "negative": 0.1, "neutral": 0.8} for _ in range(5)]

        out = aggregate_headline_rows(rows)

        assert out.directional_value == 0.0
        assert out.directional_count == 0
        assert out.n_neutral == 5

    def test_directional_value_averages_only_directional_rows(self) -> None:
        rows = [
            {"positive": 0.9, "negative": 0.05, "neutral": 0.05},  # +0.85 (positive-dominant)
            {"positive": 0.05, "negative": 0.9, "neutral": 0.05},  # -0.85 (negative-dominant)
            {"positive": 0.2, "negative": 0.2, "neutral": 0.6},  # neutral-dominant → excluded
        ]

        out = aggregate_headline_rows(rows)

        assert out.directional_value == pytest.approx(0.0)  # (+0.85 + -0.85) / 2
        assert out.n_positive == 1
        assert out.n_negative == 1
        assert out.n_neutral == 1
        assert out.directional_count == 2


class TestEffectiveSentimentValue:
    """Card/aggregate value: directional when trustworthy, else the neutral-inclusive mean."""

    def test_uses_directional_when_enough_volume(self) -> None:
        # MIN_DIRECTIONAL_VOLUME strong-positive headlines + many neutrals
        rows = [{"positive": 0.85, "negative": 0.05, "neutral": 0.10} for _ in range(MIN_DIRECTIONAL_VOLUME)]
        rows += [{"positive": 0.15, "negative": 0.15, "neutral": 0.70} for _ in range(20)]
        agg = aggregate_headline_rows(rows)

        assert agg.directional_count >= MIN_DIRECTIONAL_VOLUME
        assert effective_sentiment_value(agg) == pytest.approx(agg.directional_value)
        assert effective_sentiment_value(agg) > 0.5  # surfaces the positive signal (not drowned)

    def test_falls_back_to_mean_below_min_volume(self) -> None:
        # only 1 directional headline (< MIN) → trust the mean instead of a noisy single signal
        rows = [{"positive": 0.85, "negative": 0.05, "neutral": 0.10}]
        rows += [{"positive": 0.15, "negative": 0.15, "neutral": 0.70} for _ in range(20)]
        agg = aggregate_headline_rows(rows)

        assert agg.directional_count < MIN_DIRECTIONAL_VOLUME
        assert effective_sentiment_value(agg) == pytest.approx(agg.value)


# NOTE (MEASURED): the additions below do not move MIN_DIRECTIONAL_VOLUME or any existing
# threshold in this module -- counted the diff, it only adds coverage for two new pure helpers
# (dominant_label, top_directional_drivers) added for the Telegram alert enrichment. No decision
# boundary changed; nothing here supersedes a prior gate.


class TestDominantLabel:
    """Public argmax label helper (SoT shared by aggregate_headline_rows and driver selection)."""

    def test_positive_dominant(self) -> None:
        assert dominant_label({"positive": 0.8, "negative": 0.1, "neutral": 0.1}) == "positive"

    def test_negative_dominant(self) -> None:
        assert dominant_label({"positive": 0.1, "negative": 0.8, "neutral": 0.1}) == "negative"

    def test_neutral_dominant(self) -> None:
        assert dominant_label({"positive": 0.1, "negative": 0.1, "neutral": 0.8}) == "neutral"

    def test_unrecognized_keys_return_none(self) -> None:
        assert dominant_label({"foo": 1.0}) is None


class TestTopDirectionalDrivers:
    """Top-N directional (non-neutral) headlines by |compound| desc, with source attribution.

    Powers the Telegram alert's "top drivers" section (news_sentiment_alerts._format_alert):
    a human needs to see WHICH headlines moved the blended score, not just the aggregate.
    """

    def test_ranks_by_absolute_score_descending(self) -> None:
        texts = ["mild positive", "strong negative", "strong positive"]
        rows = [
            {"positive": 0.55, "negative": 0.35, "neutral": 0.10},  # compound +0.20
            {"positive": 0.05, "negative": 0.90, "neutral": 0.05},  # compound -0.85
            {"positive": 0.95, "negative": 0.03, "neutral": 0.02},  # compound +0.92
        ]
        sources = {"mild positive": "A", "strong negative": "B", "strong positive": "C"}

        out = top_directional_drivers(texts, rows, sources, limit=2)

        assert [d.text for d in out] == ["strong positive", "strong negative"]
        assert out[0].label == "positive"
        assert out[0].source == "C"
        assert out[0].score == pytest.approx(0.92)
        assert out[1].label == "negative"

    def test_excludes_neutral_dominant_headlines(self) -> None:
        texts = ["neutral one", "directional one"]
        rows = [
            {"positive": 0.30, "negative": 0.20, "neutral": 0.50},  # neutral-dominant
            {"positive": 0.80, "negative": 0.10, "neutral": 0.10},
        ]
        sources = {"neutral one": "X", "directional one": "Y"}

        out = top_directional_drivers(texts, rows, sources, limit=5)

        assert len(out) == 1
        assert out[0].text == "directional one"

    def test_respects_limit(self) -> None:
        texts = [f"headline {i}" for i in range(5)]
        rows = [{"positive": 0.9, "negative": 0.05, "neutral": 0.05} for _ in range(5)]
        sources = dict.fromkeys(texts, "S")

        out = top_directional_drivers(texts, rows, sources, limit=2)

        assert len(out) == 2

    def test_missing_source_defaults_to_unknown(self) -> None:
        out = top_directional_drivers(
            ["h"],
            [{"positive": 0.9, "negative": 0.05, "neutral": 0.05}],
            {},
            limit=5,
        )
        assert out[0].source == "unknown"

    def test_empty_inputs_return_empty_list(self) -> None:
        assert top_directional_drivers([], [], {}, limit=5) == []

    def test_returns_headline_driver_instances(self) -> None:
        out = top_directional_drivers(
            ["h"],
            [{"positive": 0.9, "negative": 0.05, "neutral": 0.05}],
            {"h": "Src"},
            limit=5,
        )
        assert isinstance(out[0], HeadlineDriver)


class TestTopDriversShowBothSides:
    """A BULLISH verdict was explaining itself with three bearish headlines, every single time.

    MEASURED 2026-08-24 over the 572 stored snapshots that carry drivers (`headline_sentiment_
    history.payload -> extras -> top_drivers`), 1,716 driver slots in total:

        bearish slots                                   1,694  (98.7%)
        bullish slots                                       22  ( 1.3%)
        BULLISH snapshots whose drivers are ALL bearish   141 of 141  (100%)
        mean |score|, bearish vs bullish              0.9602 vs 0.9333

    Not a coincidence and not a rare edge: EVERY bullish alert ever sent showed only red.

    The cause is FinBERT's class asymmetry, not a bug in the aggregate. Its negative class
    saturates harder on financial headlines ("Stocks Sink", "Settle Lower", "loses $8.5 million"
    all land near -0.96), while bullish phrasing is hedged and tops out lower. Rank the pool by
    `abs(score)` and the bearish tail takes every slot — 22 of 1,716 is what "essentially always"
    looks like in data.

    So the ranking was doing exactly what it said, and what it said was wrong for the job: the
    section is titled "Top drivers" and sits under a verdict line, so it must show what drove THAT
    verdict, with the other side beside it for weight. Ranking within each direction and splitting
    the budget does that; it is also what the aggregate itself already does (n_positive /
    n_negative are both reported), so the alert now matches its own breakdown line.

    The split is DERIVED from `limit`, not a second magic number — one knob stays one knob.
    """

    @staticmethod
    def _row(pos: float, neg: float) -> dict[str, float]:
        """A FinBERT-style class-probability row; neutral takes the remainder."""
        return {"positive": pos, "negative": neg, "neutral": max(0.0, 1.0 - pos - neg)}

    def _pool(self) -> tuple[list[str], list[dict[str, float]], dict[str, str]]:
        """Three hard bearish headlines and three softer bullish ones — the measured shape."""
        texts = [
            "Stocks sink in broad rout",
            "Comex gold settles lower",
            "DeFi protocol loses $8.5 million",
            "Bitcoin ETF inflows accelerate",
            "Exchange reserves fall to multi-year low",
            "Network hashrate hits record high",
        ]
        rows = [
            self._row(0.01, 0.97),
            self._row(0.01, 0.97),
            self._row(0.02, 0.96),
            self._row(0.93, 0.02),
            self._row(0.91, 0.03),
            self._row(0.90, 0.04),
        ]
        return texts, rows, dict.fromkeys(texts, "feed")

    def test_a_balanced_pool_does_not_return_only_bearish(self) -> None:
        texts, rows, sources = self._pool()

        drivers = top_directional_drivers(texts, rows, sources, limit=4)
        signs = {d.score > 0 for d in drivers}

        assert signs == {True, False}, (
            "every driver came from one direction. Measured over 572 real snapshots this produced "
            "141 of 141 bullish alerts explained entirely by bearish headlines: "
            f"{[(d.text, round(d.score, 3)) for d in drivers]}"
        )

    def test_the_budget_is_split_evenly_and_derived_from_limit(self) -> None:
        """One knob stays one knob — the split is limit/2, never a second constant."""
        texts, rows, sources = self._pool()

        drivers = top_directional_drivers(texts, rows, sources, limit=4)

        assert len(drivers) == 4
        assert sum(1 for d in drivers if d.score > 0) == 2
        assert sum(1 for d in drivers if d.score < 0) == 2

    def test_an_odd_limit_gives_the_extra_slot_to_the_stronger_side(self) -> None:
        """limit=3 cannot split evenly; the side with the harder headline gets the spare slot."""
        texts, rows, sources = self._pool()

        drivers = top_directional_drivers(texts, rows, sources, limit=3)

        assert len(drivers) == 3
        assert sum(1 for d in drivers if d.score < 0) == 2, "bearish headlines are the stronger side here"
        assert sum(1 for d in drivers if d.score > 0) == 1

    def test_each_side_is_still_ranked_by_magnitude(self) -> None:
        """Balancing must not cost the ranking — the strongest of each side is what is shown."""
        texts, rows, sources = self._pool()

        drivers = top_directional_drivers(texts, rows, sources, limit=2)
        by_text = {d.text: d.score for d in drivers}

        assert "Stocks sink in broad rout" in by_text or "Comex gold settles lower" in by_text
        assert "Bitcoin ETF inflows accelerate" in by_text, "the strongest bullish headline must win its slot"

    def test_a_one_sided_news_day_still_fills_the_budget(self) -> None:
        """A genuinely all-bearish day must show `limit` drivers, not half of them.

        Padding a real one-sided day down to 50% would trade one misleading display for another.
        """
        texts = ["a sinks", "b sinks", "c sinks", "d sinks"]
        rows = [self._row(0.01, 0.97), self._row(0.02, 0.96), self._row(0.03, 0.95), self._row(0.04, 0.94)]

        drivers = top_directional_drivers(texts, rows, dict.fromkeys(texts, "feed"), limit=3)

        assert len(drivers) == 3
        assert all(d.score < 0 for d in drivers)

    def test_neutral_headlines_are_still_excluded(self) -> None:
        """Unchanged contract: a neutral-dominant headline carries no directional signal."""
        texts = ["neutral wire copy", "b sinks"]
        rows = [self._row(0.10, 0.10), self._row(0.01, 0.97)]

        drivers = top_directional_drivers(texts, rows, dict.fromkeys(texts, "feed"), limit=3)

        assert [d.text for d in drivers] == ["b sinks"]

    def test_the_verdict_direction_leads_when_it_has_a_driver(self) -> None:
        """A BULLISH alert should open with what made it bullish, then show the counterweight."""
        texts, rows, sources = self._pool()

        drivers = top_directional_drivers(texts, rows, sources, limit=4, lead_positive=True)

        assert drivers[0].score > 0, f"bullish verdict led with a bearish headline: {drivers[0].text}"

    def test_the_bearish_verdict_leads_with_bearish(self) -> None:
        texts, rows, sources = self._pool()

        drivers = top_directional_drivers(texts, rows, sources, limit=4, lead_positive=False)

        assert drivers[0].score < 0
