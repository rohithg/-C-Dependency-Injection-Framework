-- Grain: customer dimension for relationships / slicers
CREATE OR REPLACE SECURE VIEW VW_DIM_CUSTOMER AS
SELECT
    customer_sk   AS CUSTOMER_SK,
    customer_id   AS CUSTOMER_ID,
    customer_name AS CUSTOMER_NAME,
    region_name   AS REGION_NAME,
    country_code  AS COUNTRY_CODE,
    segment       AS SEGMENT
FROM MARTS.DIM_CUSTOMER;
