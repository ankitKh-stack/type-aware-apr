def total_price(prices : list[int]) -> int:
    total = 0
    for price in prices:
        total = total + price
    return total


def parse_and_total(lines: list[str]) -> int:
    prices = [int(line.split(",")[1]) for line in lines]
    return total_price(prices)