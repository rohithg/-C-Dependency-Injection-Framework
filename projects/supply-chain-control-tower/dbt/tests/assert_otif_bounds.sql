select * from {{ ref('mart_otif_daily') }}
where otif_rate < 0 or otif_rate > 1
   or on_time_rate < 0 or on_time_rate > 1
   or in_full_rate < 0 or in_full_rate > 1
