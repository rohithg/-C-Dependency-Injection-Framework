{{
  config(
    materialized='view',
    tags=['staging', 'erp']
  )
}}

with source as (
    select * from {{ source('raw_erp', 'raw_products') }}
),

renamed as (
    select
        cast(product_id as varchar) as product_id,
        cast(sku as varchar) as sku,
        trim(product_name) as product_name,
        trim(product_category) as product_category,
        trim(product_subcategory) as product_subcategory,
        trim(brand) as brand,
        cast(unit_cost as decimal(18, 4)) as unit_cost,
        cast(list_price as decimal(18, 4)) as list_price,
        trim(unit_of_measure) as unit_of_measure,
        cast(weight_lbs as decimal(12, 4)) as weight_lbs,
        upper(trim(status)) as status,
        cast(supplier_id as varchar) as supplier_id,
        trim(supplier_name) as supplier_name,
        cast(created_at as timestamp) as created_at,
        cast(updated_at as timestamp) as updated_at,
        cast(_loaded_at as timestamp) as _loaded_at,
        cast(_source_system as varchar) as _source_system
    from source
),

deduped as (
    select
        *,
        row_number() over (
            partition by product_id
            order by updated_at desc, _loaded_at desc
        ) as _row_num
    from renamed
)

select
    product_id,
    sku,
    product_name,
    product_category,
    product_subcategory,
    brand,
    unit_cost,
    list_price,
    unit_of_measure,
    weight_lbs,
    status,
    supplier_id,
    supplier_name,
    created_at,
    updated_at,
    _loaded_at,
    _source_system
from deduped
where _row_num = 1
