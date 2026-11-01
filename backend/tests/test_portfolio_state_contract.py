import json
import unittest

from backend.core.schemas import PortfolioState


class TestPortfolioStateContract(unittest.TestCase):
    def test_legacy_json_omitting_exposure_and_timestamp_fields_decodes_cleanly(self):
        legacy_dict = {
            "initial_equity_usd": 10000.0,
            "current_equity_usd": 9850.0,
            "high_water_mark_usd": 10500.0,
            "daily_start_equity_usd": 10000.0,
            "asset_exposures_usd": {"SOL-USDT": 1500.0},
            "pod_exposures_usd": {"pod_carry": 1500.0},
        }
        legacy_json = json.dumps(legacy_dict)
        data = json.loads(legacy_json)
        state = PortfolioState.from_dict(data)

        self.assertEqual(state.initial_equity_usd, 10000.0)
        self.assertEqual(state.current_equity_usd, 9850.0)
        self.assertEqual(state.high_water_mark_usd, 10500.0)
        self.assertEqual(state.daily_start_equity_usd, 10000.0)
        self.assertEqual(state.asset_exposures_usd, {"SOL-USDT": 1500.0})
        self.assertEqual(state.pod_exposures_usd, {"pod_carry": 1500.0})
        self.assertEqual(state.gross_exposure_usd, 0.0)
        self.assertEqual(state.last_order_ts_ms, {})

    def test_roundtrip_preserves_exposure_maps_and_timestamps(self):
        state = PortfolioState(
            initial_equity_usd=10000.0,
            current_equity_usd=10250.0,
            high_water_mark_usd=10500.0,
            daily_start_equity_usd=10000.0,
            asset_exposures_usd={"SOL-USDT": 1500.0, "BTC-USDT": -800.0},
            pod_exposures_usd={"pod_carry": 1500.0, "pod_momentum": 800.0},
            gross_exposure_usd=5000.0,
            last_order_ts_ms={"pod_carry:SOL-USDT": 1792180000123},
        )
        serialized = state.to_dict()
        json_str = json.dumps(serialized)
        decoded = PortfolioState.from_dict(json.loads(json_str))

        self.assertEqual(decoded.initial_equity_usd, 10000.0)
        self.assertEqual(decoded.current_equity_usd, 10250.0)
        self.assertEqual(decoded.high_water_mark_usd, 10500.0)
        self.assertEqual(decoded.daily_start_equity_usd, 10000.0)
        self.assertEqual(
            decoded.asset_exposures_usd,
            {"SOL-USDT": 1500.0, "BTC-USDT": -800.0},
        )
        self.assertEqual(
            decoded.pod_exposures_usd,
            {"pod_carry": 1500.0, "pod_momentum": 800.0},
        )
        self.assertEqual(decoded.gross_exposure_usd, 5000.0)
        self.assertEqual(
            decoded.last_order_ts_ms,
            {"pod_carry:SOL-USDT": 1792180000123},
        )

    def test_python_portfolio_state_to_dict_contains_all_eight_keys(self):
        state = PortfolioState(
            initial_equity_usd=10000.0,
            current_equity_usd=10000.0,
            high_water_mark_usd=10000.0,
            daily_start_equity_usd=10000.0,
        )
        d = state.to_dict()
        expected_keys = {
            "initial_equity_usd",
            "current_equity_usd",
            "high_water_mark_usd",
            "daily_start_equity_usd",
            "asset_exposures_usd",
            "pod_exposures_usd",
            "gross_exposure_usd",
            "last_order_ts_ms",
        }
        self.assertEqual(set(d.keys()), expected_keys)
        self.assertEqual(d["asset_exposures_usd"], {})
        self.assertEqual(d["pod_exposures_usd"], {})
        self.assertEqual(d["gross_exposure_usd"], 0.0)
        self.assertEqual(d["last_order_ts_ms"], {})


if __name__ == "__main__":
    unittest.main()
