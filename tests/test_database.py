from backend.services.database import (
    create_user,
    get_account_reputation,
    list_transactions,
    save_transaction,
    update_account_reputation,
)


def test_user_transaction_and_reputation_persistence(isolated_database):
    ok, _, user = create_user("alice", "StrongPass1")
    assert ok is True
    assert user["account_id"] == "C100000001"

    saved = save_transaction(
        user_id=user["id"], sender=user["account_id"], receiver="M1", amount=250,
        transaction_type="PAYMENT", probability=0.35, prediction=1,
        risk_level="MEDIUM", explanation={"reasons": ["Test reason"]},
    )
    reputation = update_account_reputation(user["account_id"], 250, 0.35, 1, False)

    assert saved["risk_level"] == "MEDIUM"
    assert len(list_transactions(user_id=user["id"])) == 1
    assert reputation["transaction_count"] == 1
    assert get_account_reputation(user["account_id"])["fraud_count"] == 1


def test_duplicate_username_is_rejected(isolated_database):
    assert create_user("alice", "StrongPass1")[0] is True
    assert create_user("alice", "StrongPass1")[0] is False

