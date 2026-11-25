"""Chạy: python -m unittest discover -s tools/tests"""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from detection_time import analyse, invalid_reason, summary  # noqa: E402


def event(fid, t0, rec, status="completed", **kw):
    return {"fault_id": fid, "case": "dừng nginx", "scenario": "service-stop:nginx", "target": "web", "params": {},
            "expected_alerts": ["NginxDown", "ServiceDown", "EndpointDown"], "root_alert": "NginxDown",
            "match_labels": {"host": "web"}, "injected_ts": t0, "injected_ts_receiver": t0,
            "recovered_ts_receiver": rec, "status": status, "data_gap": False, **kw}


def alert(name, ts, status="firing", inst="web", host="web", delay=5.0):
    return {"alertname": name, "status": status, "received_ts": ts, "fingerprint": name + inst,
            "startsAt": datetime.fromtimestamp(ts - delay, tz=timezone.utc).isoformat(), "labels": {"host": host, "instance": inst}}


def one(events, alerts):
    return analyse(events, alerts, window=900, tolerance=2)[0]


class InvalidReason(unittest.TestCase):
    def test_statuses(self):
        self.assertEqual(invalid_reason(event("a", 0, 10)), "")
        self.assertIn("Ctrl+C", invalid_reason(event("a", 0, 10, "aborted", stop_reason="người dùng ngắt (Ctrl+C)")))
        self.assertIn("script chết", invalid_reason(event("a", 0, None, "running")))
        self.assertIn("mất dữ liệu", invalid_reason({**event("a", 0, 10), "data_gap": True}))

    def test_events_before_status_field(self):
        old = event("a", 0, 10)
        del old["status"]
        self.assertEqual(invalid_reason({**old, "stop_reason": "đã nhận cảnh báo gốc"}), "")
        self.assertIn("ngắt", invalid_reason({**old, "stop_reason": "người dùng ngắt (Ctrl+C)"}))
        self.assertIn("script chết", invalid_reason({**old, "stop_reason": None}))


    def test_rule_evaluation_lag(self):
        self.assertIn("SC-04", invalid_reason(event("a", 0, 10, eval_lag_s=10.4)))
        self.assertEqual(invalid_reason(event("a", 0, 10, eval_lag_s=0.02), 9.0), "")
        late = one([event("a", 1000, 1100)], [alert("NginxDown", 1060, delay=10.4)])   # sự kiện cũ, chưa có eval_lag_s
        self.assertEqual(late["valid"], "no")
        self.assertEqual(one([event("a", 1000, 1100)], [alert("NginxDown", 1060)])["valid"], "yes")


class Analyse(unittest.TestCase):
    def test_first_root_and_order(self):
        r = one([event("a", 1000, 1100)], [alert("EndpointDown", 1042, inst="web:80"), alert("NginxDown", 1062),
                                          alert("ServiceDown", 1070), alert("NginxDown", 1160, "resolved")])
        self.assertEqual((r["first_alert"], r["first_s"], r["root_s"], r["root_resolved_s"]), ("EndpointDown", 42.0, 62.0, 60.0))
        self.assertIn("EndpointDown[web:80]", r["extra_before_root"])
        self.assertIn("ServiceDown", r["extra_after_root"])

    def test_alert_after_recovery_is_noise_not_detection(self):
        r = one([event("a", 1000, 1100)], [alert("EndpointDown", 1110)])
        self.assertEqual((r["detected"], r["valid"]), ("no", "yes"))
        self.assertIn("EndpointDown", r["recover_noise"])

    def test_resent_alert_counted_once(self):
        r = one([event("a", 1000, 1100)], [alert("EndpointDown", 1040), alert("EndpointDown", 1070), alert("NginxDown", 1060)])
        self.assertEqual((r["extra_before_root"].count("EndpointDown"), r["extra_after_root"]), (1, ""))

    def test_other_host_is_unrelated(self):
        r = one([event("a", 1000, 1100)], [alert("EndpointDown", 1040, inst="db:5432", host="db")])
        self.assertEqual(r["detected"], "no")
        self.assertIn("db:5432", r["unrelated_alerts"])

    def test_window_stops_at_next_event_even_if_invalid(self):
        r = one([event("a", 1000, 1100), event("b", 1200, None, "running")], [alert("NginxDown", 1250)])
        self.assertEqual((r["detected"], r["recover_noise"]), ("no", ""))

    def test_summary_ignores_nothing_it_is_given(self):
        rows = analyse([event("a", 1000, 1100), event("b", 2000, 2100)], [alert("NginxDown", 1060)], 900, 2)
        self.assertEqual(summary(rows, "root_s")[0][1:4], [2, 1, 1])


if __name__ == "__main__":
    unittest.main()
