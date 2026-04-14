"""Unit tests for circular genome coordinate methods."""

import pytest
from mitoflow.models.genome import GenomeSequence


@pytest.fixture
def genome_500k():
    """500kb circular genome for testing."""
    return GenomeSequence(seqid="test", sequence="A" * 500000)


@pytest.fixture
def genome_100k():
    """100kb circular genome for testing."""
    return GenomeSequence(seqid="test", sequence="A" * 100000)


class TestCircularDistance:
    def test_basic_distance(self, genome_500k):
        assert genome_500k.circular_distance(100, 200) == 100

    def test_same_position(self, genome_500k):
        assert genome_500k.circular_distance(5000, 5000) == 0

    def test_wrap_around(self, genome_500k):
        # 499000 -> 1000: |499000-1000|=498000, 500000-498000=2000
        assert genome_500k.circular_distance(499000, 1000) == 2000

    def test_symmetry(self, genome_500k):
        a, b = 499000, 1000
        assert genome_500k.circular_distance(a, b) == genome_500k.circular_distance(b, a)

    def test_opposite_sides(self, genome_100k):
        # 1 and 50001 are diametrically opposite on 100kb genome
        assert genome_100k.circular_distance(1, 50001) == 50000

    def test_origin_adjacent(self, genome_500k):
        # Positions on either side of origin
        assert genome_500k.circular_distance(500000, 1) == 1


class TestCircularSpan:
    def test_forward_span(self, genome_500k):
        # 100 to 200 inclusive = 101 positions
        assert genome_500k.circular_span(100, 200) == 101

    def test_single_position(self, genome_500k):
        assert genome_500k.circular_span(5000, 5000) == 1

    def test_wrap_around_span(self, genome_500k):
        # 499000 -> 1000 crossing origin
        # = (500000-499000+1) + 1000 = 1001 + 1000 = 2001
        assert genome_500k.circular_span(499000, 1000) == 2001

    def test_full_genome_span(self, genome_500k):
        assert genome_500k.circular_span(1, 500000) == 500000

    def test_near_origin_wrap(self, genome_100k):
        assert genome_100k.circular_span(99999, 2) == 4


class TestWrapPosition:
    def test_normal_position(self, genome_500k):
        assert genome_500k.wrap_position(250000) == 250000

    def test_first_position(self, genome_500k):
        assert genome_500k.wrap_position(1) == 1

    def test_exact_length(self, genome_500k):
        assert genome_500k.wrap_position(500000) == 500000

    def test_overflow(self, genome_500k):
        assert genome_500k.wrap_position(500001) == 1

    def test_double_overflow(self, genome_500k):
        assert genome_500k.wrap_position(1000001) == 1

    def test_zero(self, genome_500k):
        assert genome_500k.wrap_position(0) == 500000

    def test_negative(self, genome_500k):
        assert genome_500k.wrap_position(-1) == 499999


class TestCircularPositionsBetween:
    def test_forward_range(self, genome_500k):
        positions = genome_500k.circular_positions_between(100, 103)
        assert positions == [100, 101, 102, 103]

    def test_wrap_around(self, genome_500k):
        positions = genome_500k.circular_positions_between(499999, 2)
        assert positions == [499999, 500000, 1, 2]

    def test_single_position(self, genome_500k):
        positions = genome_500k.circular_positions_between(5000, 5000)
        assert positions == [5000]
