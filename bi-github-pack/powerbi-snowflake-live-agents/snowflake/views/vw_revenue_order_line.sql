-- Grain: one row per order line (live DirectQuery fact)
-- Drill columns: REGION_NAME, PRODUCT_CATEGORY, PRODUCT_NAME, CUSTOMER_NAME
CREATE OR REPLACE SECURE VIEW VW_REVENUE_ORDER_LINE AS
SELECT
    ol.order_line_id          AS ORDER_LINE_ID,
    ol.order_id               AS ORDER_ID,
    ol.order_date             AS ORDER_DATE,
    DATE_TRUNC('day', ol.order_date)::DATE AS ORDER_DAY,
    c.customer_id             AS CUSTOMER_ID,
    c.customer_name           AS CUSTOMER_NAME,
    c.region_name             AS REGION_NAME,
    c.country_code            AS COUNTRY_CODE,
    p.product_id              AS PRODUCT_ID,
    p.product_name            AS PRODUCT_NAME,
    p.product_category        AS PRODUCT_CATEGORY,
    ol.order_channel          AS ORDER_CHANNEL,
    ol.quantity               AS QUANTITY,
    ol.line_net_amount        AS NET_REVENUE,
    ol.line_cogs              AS COGS,
    ol.line_gross_margin      AS GROSS_MARGIN,
    DIV0(ol.line_gross_margin, NULLIF(ol.line_net_amount, 0)) AS MARGIN_PCT,
    ol.currency_code          AS CURRENCY_CODE
FROM MARTS.FCT_ORDERS ol
JOIN MARTS.DIM_CUSTOMER c
  ON ol.customer_sk = c.customer_sk
JOIN MARTS.DIM_PRODUCT p
  ON ol.product_sk = p.product_sk
WHERE ol.order_status NOT IN ('CANCELLED', 'VOID');
