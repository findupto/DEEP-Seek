from decimal import Decimal
from enterprise_production import money, fixed_asset_monthly_depreciation, aging_bucket

def test_money_rounding(): assert money('12.345') == Decimal('12.35')
def test_depreciation(): assert fixed_asset_monthly_depreciation('1200','200',10) == Decimal('100.00')
def test_aging(): assert aging_bucket(10)=='0-30'; assert aging_bucket(75)=='61-90'; assert aging_bucket(200)=='120+'
