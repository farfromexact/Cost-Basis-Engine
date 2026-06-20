from data.eastmoney import infer_secid, parse_eastmoney_trends


def test_infer_secid_for_common_a_share_codes() -> None:
    assert infer_secid("600519") == "1.600519"
    assert infer_secid("000001") == "0.000001"
    assert infer_secid("300750") == "0.300750"
    assert infer_secid("SH.600519") == "1.600519"
    assert infer_secid("000001.SZ") == "0.000001"


def test_parse_eastmoney_trends_payload() -> None:
    payload = {
        "data": {
            "trends": [
                "2026-06-18 09:30,10.00,10.02,10.03,9.99,1000,10020.00,10.02",
                "2026-06-18 09:31,10.02,10.01,10.04,10.00,1200,12012.00,10.015",
            ]
        }
    }

    bars = parse_eastmoney_trends(payload)

    assert len(bars) == 2
    assert bars[0].ts.strftime("%H:%M") == "09:30"
    assert bars[0].open == 10.00
    assert bars[1].volume == 120000
