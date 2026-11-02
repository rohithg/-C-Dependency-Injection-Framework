from __future__ import annotations

import json
from pathlib import Path


def seed_complex_sources(root: Path) -> None:
    raw = root / "data" / "raw"
    cdc = root / "data" / "cdc"
    raw.mkdir(parents=True, exist_ok=True)
    cdc.mkdir(parents=True, exist_ok=True)

    (raw / "customers.csv").write_text(
        """customer_id,customer_name,region_name,country_code,segment,credit_tier
C001,Acme Logistics,west,us,ENTERPRISE,A
C002,Bay Area Foods,west,us,SMB,B
C003,Midwest Parts Co,central,us,ENTERPRISE,A
C004,Atlantic Retail,east,us,SMB,C
C005,Lone Star Supply,south,us,ENTERPRISE,A
,Bad Null Customer,west,us,SMB,B
""",
        encoding="utf-8",
    )

    # second snapshot for SCD2 change (name + credit tier)
    (raw / "customers_day2.csv").write_text(
        """customer_id,customer_name,region_name,country_code,segment,credit_tier
C001,Acme Logistics International,west,us,ENTERPRISE,AA
C002,Bay Area Foods,west,us,SMB,B
C003,Midwest Parts Co,central,us,ENTERPRISE,A
C004,Atlantic Retail,east,us,SMB,B
C005,Lone Star Supply,south,us,ENTERPRISE,A
C006,Pacific Nano,west,us,ENTERPRISE,A
""",
        encoding="utf-8",
    )

    (raw / "products.csv").write_text(
        """product_id,product_name,product_category,brand,unit_cost,is_active
P100,Industrial Pallet Jack,Material Handling,LiftCo,220.00,true
P200,Cold Chain Tote,Packaging,FrostPack,12.50,true
P300,RFID Dock Reader,IoT,SignalWare,480.00,true
P400,Stretch Wrap Roll,Packaging,WrapRight,8.25,true
P500,Safety Vest Bulk Pack,PPE,SafeWear,18.00,true
P600,Bad Cost Product,IoT,X,,true
""",
        encoding="utf-8",
    )

    (raw / "orders.csv").write_text(
        """order_id,customer_id,order_date,order_status,order_channel,currency_code
O9001,C001,2026-01-05,SHIPPED,Direct,USD
O9002,C002,2026-01-06,SHIPPED,Marketplace,USD
O9003,C003,2026-01-07,OPEN,Direct,EUR
O9004,C004,2026-01-08,CANCELLED,Direct,USD
O9005,C005,2026-01-09,SHIPPED,Partner,USD
O9006,C002,2026-02-01,SHIPPED,Marketplace,GBP
O9007,C001,2026-02-03,DELIVERED,Direct,USD
""",
        encoding="utf-8",
    )

    (raw / "order_lines.csv").write_text(
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
L11,O9002,P100,0,349.00,0.00,0
L12,O9007,P999,2,10.00,0.00,0
""",
        encoding="utf-8",
    )

    # promotions bridge (many-to-many style)
    (raw / "order_promotions.json").write_text(
        json.dumps(
            [
                {"order_id": "O9001", "promo_code": "NEWYEAR5", "promo_type": "PERCENT"},
                {"order_id": "O9001", "promo_code": "FREESHIP", "promo_type": "SHIPPING"},
                {"order_id": "O9006", "promo_code": "UKLAUNCH", "promo_type": "PERCENT"},
                {"order_id": "O9007", "promo_code": "LOYAL10", "promo_type": "PERCENT"},
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    # CDC: update O9003 to SHIPPED, insert O9008, delete phantom
    lines = [
        {
            "op": "U",
            "commit_ts": "2026-02-10T12:00:00Z",
            "order_id": "O9003",
            "customer_id": "C003",
            "order_date": "2026-01-07",
            "order_status": "SHIPPED",
            "order_channel": "Direct",
            "currency_code": "EUR",
        },
        {
            "op": "I",
            "commit_ts": "2026-02-11T09:30:00Z",
            "order_id": "O9008",
            "customer_id": "C006",
            "order_date": "2026-02-11",
            "order_status": "OPEN",
            "order_channel": "Direct",
            "currency_code": "USD",
        },
        {
            "op": "D",
            "commit_ts": "2026-02-11T10:00:00Z",
            "order_id": "O9999",
            "customer_id": None,
            "order_date": None,
            "order_status": None,
            "order_channel": None,
            "currency_code": None,
        },
    ]
    (cdc / "orders_cdc.jsonl").write_text(
        "\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8"
    )
