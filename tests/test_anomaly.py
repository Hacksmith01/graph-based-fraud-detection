from backend.services.anomaly import TransactionAnomalyDetector


def test_anomaly_detector_returns_stable_shape():
    detector = TransactionAnomalyDetector()
    result = detector.score(1_000_000)

    assert isinstance(result["is_anomaly"], bool)
    assert isinstance(result["anomaly_score"], float)
    detector.add_amount(1_000_000)

