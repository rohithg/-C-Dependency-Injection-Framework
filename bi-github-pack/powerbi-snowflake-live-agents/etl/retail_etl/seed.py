from __future__ import annotations

from pathlib import Path


CUSTOMERS = """customer_id,customer_name,region_name,country_code,segment,is_active
C001,Acme Logistics,west,us,ENTERPRISE,true
C002,Bay Area Foods,west,us,SMB,yes
C003,Midwest Parts Co,central,us,ENTERPRISE,1
C004,Atlantic Retail,east,us,SMB,true
C005,Lone Star Supply,south,us,ENTERPRISE,true
C006,Duplicate Name Inc,west,us,SMB,false
C001,Acme Logistics Updated,West,US,ENTERPRISE,true
"""

PRODUCTS = """product_id,product_name,product_category,brand,unit_cost
P100,Industrial Pallet Jack,Material Handling,LiftCo,220.00
P200,Cold Chain Tote,Packaging,FrostPack,12.50
P300,RFID Dock Reader,IoT,SignalWare,480.00
P400,Stretch Wrap Roll,Packaging,WrapRight,8.25
P500,Safety Vest Bulk Pack,PPE,SafeWear,18.00
"""

ORDERS = """order_id,customer_id,order_date,order_status,order_channel,currency_code
O9001,C001,2026-01-05,SHIPPED,Direct,USD
O9002,C002,2026-01-06,SHIPPED,Marketplace,USD
O9003,C003,2026-01-07,OPEN,Direct,USD
O9004,C004,2026-01-08,CANCELLED,Direct,USD
O9005,C005,2026-01-09,SHIPPED,Partner,USD
O9006,C002,2026-02-01,SHIPPED,Marketplace,USD
O9007,C001,2026-02-03,SHIPPED,Direct,USD
"""

ORDER_LINES = """order_line_id,order_id,product_id,quantity,unit_price,discount_pct,tax_amount
L1,O9001,P100,4,349.00,0.05,55.84
L2,O9001,P400,20,14.99,0.00,23.98
L3,O9002,P200,100,19.50,0.10,156.00
L4,O9003,P300,2,799.00,0.00,127.84
L5,O9004,P500,10,29.00,0.00,23.20
L6,O9005,P100,1,349.00,0.00,27.92
L7,O9005,P300,1,799.00,0.15,108.66
L8,O9006,P200,50,19.50,0.05,74.10
L9,O9007,P400,40,14.99,0.00,47.97
L10,O9007,P500,5,29.00,0.00,11.60
L11,O9002,P100,0,349.00,0.00,0
"""


def write_seed_data(raw_dir: Path) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "customers.csv").write_text(CUSTOMERS.lstrip(), encoding="utf-8")
    (raw_dir / "products.csv").write_text(PRODUCTS.lstrip(), encoding="utf-8")
    (raw_dir / "orders.csv").write_text(ORDERS.lstrip(), encoding="utf-8")
    (raw_dir / "order_lines.csv").write_text(ORDER_LINES.lstrip(), encoding="utf-8")
