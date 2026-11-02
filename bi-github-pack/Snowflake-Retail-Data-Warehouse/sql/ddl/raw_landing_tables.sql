-- =============================================================================
-- Snowflake RAW landing DDL — Retail / Supply Chain ELT
-- Sources: NetSuite (ERP/Finance), CRM customers, TMS shipments, YMS locations
-- Run once (or via migration tooling) before Airflow extract / dbt seed.
-- =============================================================================

create database if not exists retail_dw;
create schema if not exists retail_dw.raw;
create schema if not exists retail_dw.staging;
create schema if not exists retail_dw.intermediate;
create schema if not exists retail_dw.marts;
create schema if not exists retail_dw.analytics;

create warehouse if not exists transform_wh
    with warehouse_size = 'xsmall'
    auto_suspend = 60
    auto_resume = true
    initially_suspended = true;

-- -----------------------------------------------------------------------------
-- ERP / CRM (NetSuite-style)
-- -----------------------------------------------------------------------------

create table if not exists retail_dw.raw.raw_customers (
    customer_id             varchar(32)     not null,
    customer_code           varchar(64),
    customer_name           varchar(256),
    customer_type           varchar(32),
    industry                varchar(64),
    email                   varchar(256),
    phone                   varchar(64),
    billing_city            varchar(128),
    billing_state           varchar(64),
    billing_country         varchar(64),
    shipping_city           varchar(128),
    shipping_state          varchar(64),
    shipping_country        varchar(64),
    credit_limit            number(18, 2),
    status                  varchar(32),
    account_manager         varchar(128),
    created_at              timestamp_ntz,
    updated_at              timestamp_ntz,
    _loaded_at              timestamp_ntz   not null default current_timestamp(),
    _source_system          varchar(64)     default 'NETSUITE',
    constraint pk_raw_customers primary key (customer_id)
);

create table if not exists retail_dw.raw.raw_products (
    product_id              varchar(32)     not null,
    sku                     varchar(64),
    product_name            varchar(256),
    product_category        varchar(64),
    product_subcategory     varchar(64),
    brand                   varchar(64),
    unit_cost               number(18, 4),
    list_price              number(18, 4),
    unit_of_measure         varchar(16),
    weight_lbs              number(12, 4),
    status                  varchar(32),
    supplier_id             varchar(32),
    supplier_name           varchar(256),
    created_at              timestamp_ntz,
    updated_at              timestamp_ntz,
    _loaded_at              timestamp_ntz   not null default current_timestamp(),
    _source_system          varchar(64)     default 'NETSUITE',
    constraint pk_raw_products primary key (product_id)
);

create table if not exists retail_dw.raw.raw_orders (
    order_id                varchar(32)     not null,
    order_line_id           varchar(32)     not null,
    order_number            varchar(64),
    customer_id             varchar(32),
    product_id              varchar(32),
    order_date              date,
    requested_ship_date     date,
    order_status            varchar(32),
    order_channel           varchar(32),
    quantity                number(12, 0),
    unit_price              number(18, 4),
    discount_pct            number(7, 4),
    tax_amount              number(18, 4),
    ship_from_location_id   varchar(32),
    ship_to_location_id     varchar(32),
    currency_code           varchar(8),
    sales_rep               varchar(128),
    created_at              timestamp_ntz,
    updated_at              timestamp_ntz,
    _loaded_at              timestamp_ntz   not null default current_timestamp(),
    _source_system          varchar(64)     default 'NETSUITE',
    constraint pk_raw_orders primary key (order_line_id)
);

create table if not exists retail_dw.raw.raw_invoices (
    invoice_id              varchar(32)     not null,
    invoice_number          varchar(64),
    order_id                varchar(32),
    customer_id             varchar(32),
    invoice_date            date,
    due_date                date,
    paid_date               date,
    invoice_status          varchar(32),
    subtotal_amount         number(18, 2),
    tax_amount              number(18, 2),
    freight_amount          number(18, 2),
    total_amount            number(18, 2),
    amount_paid             number(18, 2),
    currency_code           varchar(8),
    payment_terms_days      number(6, 0),
    created_at              timestamp_ntz,
    updated_at              timestamp_ntz,
    _loaded_at              timestamp_ntz   not null default current_timestamp(),
    _source_system          varchar(64)     default 'NETSUITE',
    constraint pk_raw_invoices primary key (invoice_id)
);

-- -----------------------------------------------------------------------------
-- Logistics (TMS / YMS)
-- -----------------------------------------------------------------------------

create table if not exists retail_dw.raw.raw_locations (
    location_id             varchar(32)     not null,
    location_code           varchar(64),
    location_name           varchar(256),
    location_type           varchar(32),
    address_line1           varchar(256),
    city                    varchar(128),
    state_province          varchar(64),
    postal_code             varchar(32),
    country                 varchar(64),
    region                  varchar(64),
    time_zone               varchar(64),
    is_active               boolean,
    square_footage          number(12, 0),
    dock_door_count         number(6, 0),
    created_at              timestamp_ntz,
    updated_at              timestamp_ntz,
    _loaded_at              timestamp_ntz   not null default current_timestamp(),
    _source_system          varchar(64)     default 'YMS',
    constraint pk_raw_locations primary key (location_id)
);

create table if not exists retail_dw.raw.raw_shipments (
    shipment_id             varchar(32)     not null,
    shipment_number         varchar(64),
    order_id                varchar(32),
    carrier_code            varchar(32),
    carrier_name            varchar(128),
    mode                    varchar(32),
    shipment_status         varchar(32),
    origin_location_id      varchar(32),
    destination_location_id varchar(32),
    planned_ship_date       date,
    actual_ship_date        date,
    planned_delivery_date   date,
    actual_delivery_date    date,
    freight_cost            number(18, 2),
    weight_lbs              number(12, 4),
    pallet_count            number(6, 0),
    tracking_number         varchar(128),
    yard_checkin_at         timestamp_ntz,
    yard_checkout_at        timestamp_ntz,
    created_at              timestamp_ntz,
    updated_at              timestamp_ntz,
    _loaded_at              timestamp_ntz   not null default current_timestamp(),
    _source_system          varchar(64)     default 'TMS',
    constraint pk_raw_shipments primary key (shipment_id)
);

-- Helpful clustering for incremental ELT filters
alter table retail_dw.raw.raw_orders cluster by (order_date);
alter table retail_dw.raw.raw_shipments cluster by (actual_ship_date);
alter table retail_dw.raw.raw_invoices cluster by (invoice_date);
