select carrier, sum(shipments) as shipments,
  sum(otif_rate * shipments) / nullif(sum(shipments),0) as weighted_otif
from {{ ref('mart_otif_daily') }}
group by 1 order by weighted_otif asc
