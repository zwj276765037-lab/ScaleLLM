import sys
from pathlib import Path
from fractions import Fraction
import random
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiment'))
from exact_oracle import common_binary_sum, decode_fraction, evaluate_exact, round_rational_away


def group(dot, shift, code_a=1, code_w=1):
    return dict(dot=dot, act_code=code_a, weight_code=code_w,
                act_shift=shift // 2, weight_shift=shift - shift // 2)


class ExactOracleTests(unittest.TestCase):
    def test_signed_half_and_adjacent_integer_ratios(self):
        for sign in (-1, 1):
            for numerator, expected in ((127, 0), (128, 1), (129, 1), (383, 1), (384, 2)):
                self.assertEqual(round_rational_away(sign * numerator, 256), sign * expected)
        for bad in (True, 1.0):
            with self.assertRaises(TypeError):
                round_rational_away(bad, 2)
        with self.assertRaises(ValueError):
            round_rational_away(1, 0)

    def test_common_denominator_preserves_tiny_cancellation(self):
        groups = [group((1 << 80) + 1, 12), group(-(1 << 80), 12), group(-1, 126)]
        numerator, bits = common_binary_sum(groups)
        self.assertEqual(bits, 126)
        self.assertEqual(Fraction(numerator, 1 << bits), Fraction(1, 1 << 12) - Fraction(1, 1 << 126))
        self.assertEqual(numerator, (1 << 114) - 1)

    def test_round_once_has_no_intermediate_f24_loss(self):
        groups = [group(255, 25), group(1, 25)]
        result = evaluate_exact({'groups': groups}, 24)
        self.assertEqual(result['output_only']['output_code'], 1)
        self.assertEqual(decode_fraction(result['exact']), Fraction(1, 1 << 17))

    def test_s32_output_limit_and_half_lsb(self):
        for code in ((1 << 31) - 1, 1 << 31, -(1 << 31), -(1 << 31) - 1):
            result = evaluate_exact({'groups': [group(code, 16)]}, 32)
            self.assertEqual(result['output_only']['pre_saturation_code'], code)
            self.assertEqual(result['output_only']['saturated'], not -(1 << 31) <= code < 1 << 31)

    def test_fraction_crosscheck_random_unbounded_integers(self):
        rng = random.Random(20261019)
        for _ in range(300):
            groups = [group(rng.randrange(-(1 << 75), 1 << 75), rng.randrange(0, 127),
                            rng.randrange(256), rng.randrange(256)) for _ in range(rng.randrange(1, 20))]
            independent = sum((Fraction(g['dot'] * g['act_code'] * g['weight_code'],
                                        1 << (g['act_shift'] + g['weight_shift'])) for g in groups), Fraction())
            result = evaluate_exact({'groups': groups}, 32)
            self.assertEqual(decode_fraction(result['exact']), independent)
            scaled = abs(independent) * (1 << 16)
            expected = scaled.numerator // scaled.denominator
            expected += int(scaled - expected >= Fraction(1, 2))
            expected *= -1 if independent < 0 else 1
            self.assertEqual(result['output_only']['pre_saturation_code'], expected)


if __name__ == '__main__':
    unittest.main()
