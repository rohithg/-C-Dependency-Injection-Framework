select * from {{ ref('mart_short_ship_exceptions') }}
where short_qty <= 0
