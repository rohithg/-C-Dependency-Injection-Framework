from __future__ import annotations

from pathlib import Path


def seed_senior_landing(root: Path) -> None:
    landing = root / "data" / "landing"
    landing.mkdir(parents=True, exist_ok=True)

    (landing / "customers.csv").write_text(
        """customer_id,customer_name,email,phone,region_name,country_code,segment,credit_tier,valid_from
C001,Acme Logistics,ops@acme.example,555-0100,West,US,ENTERPRISE,A,2026-01-01
C002,Bay Area Foods,hello@bay.example,555-0101,West,US,SMB,B,2026-01-01
C003,Midwest Parts,parts@mw.example,555-0102,Central,US,ENTERPRISE,A,2026-01-01
C004,Atlantic Retail,buy@atl.example,555-0103,East,US,SMB,C,2026-01-01
C005,Lone Star Supply,ls@tx.example,555-0104,South,US,ENTERPRISE,A,2026-01-01
""",
        encoding="utf-8",
    )

    (landing / "products.csv").write_text(
        """product_id,product_name,product_category,brand,unit_cost,is_active,valid_from
P100,Industrial Pallet Jack,Material Handling,LiftCo,220.00,true,2026-01-01
P200,Cold Chain Tote,Packaging,FrostPack,12.50,true,2026-01-01
P300,RFID Dock Reader,IoT,SignalWare,480.00,true,2026-01-01
P400,Stretch Wrap Roll,Packaging,WrapRight,8.25,true,2026-01-01
P500,Safety Vest Bulk Pack,PPE,SafeWear,18.00,true,2026-01-01
""",
        encoding="utf-8",
    )

    (landing / "orders.csv").write_text(
        """order_id,customer_id,order_date,order_status,order_channel,currency_code,promised_ship_date,actual_ship_date,delivered_date
O9001,C001,2026-01-05,SHIPPED,Direct,USD,2026-01-07,2026-01-08,2026-01-12
O9002,C002,2026-01-06,SHIPPED,Marketplace,USD,2026-01-08,2026-01-08,2026-01-11
O9003,C003,2026-01-07,OPEN,Direct,EUR,2026-01-10,,
O9004,C004,2026-01-08,CANCELLED,Direct,USD,2026-01-10,,
O9005,C005,2026-01-09,SHIPPED,Partner,USD,2026-01-11,2026-01-13,2026-01-18
O9006,C002,2026-02-01,SHIPPED,Marketplace,GBP,2026-02-03,2026-02-04,2026-02-09
O9007,C001,2026-02-03,DELIVERED,Direct,USD,2026-02-05,2026-02-05,2026-02-07
""",
        encoding="utf-8",
    )

    (landing / "order_lines.csv").write_text(
        """order_line_id,order_id,product_id,quantity,unit_price,discount_pct,tax_amount
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
L11,O9007,P999,1,99.00,0.00,7.92
""",
        encoding="utf-8",
    )

    (landing / "fx_rates.csv").write_text(
        """as_of_date,from_currency,to_currency,rate
2026-01-01,EUR,USD,1.08
2026-01-01,GBP,USD,1.27
2026-02-01,EUR,USD,1.09
2026-02-01,GBP,USD,1.26
""",
        encoding="utf-8",
    )
