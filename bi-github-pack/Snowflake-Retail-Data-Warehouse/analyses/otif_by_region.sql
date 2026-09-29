-- On-time delivery by origin region (portfolio analysis query).

select
    coalesce(origin_region, 'UNKNOWN') as region,
    count(*) as shipment_count,
    sum(case when is_on_time then 1 else 0 end) as on_time_count,
    round(
        sum(case when is_on_time then 1 else 0 end)::float
        / nullif(count(*), 0),
        3
    ) as otif_rate,
    avg(yard_dwell_hours) as avg_yard_dwell_hours
from {{ ref('fct_shipments') }}
where shipment_status in ('DELIVERED', 'CLOSED', 'IN_TRANSIT', 'EXCEPTION')
group by 1
order by otif_rate asc
