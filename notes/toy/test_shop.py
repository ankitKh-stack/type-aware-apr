from shop import parse_and_total, total_price


def test_total_price():
    assert total_price([10, 20]) == 30


def test_parse_and_total():
    assert parse_and_total(["apple,10", "pear,20"]) == 30