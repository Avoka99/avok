from app.models.wallet import WalletType


def test_wallet_type_enum_values():
    assert WalletType.MAIN.value == "main"
    assert WalletType.ESCROW.value == "escrow"
