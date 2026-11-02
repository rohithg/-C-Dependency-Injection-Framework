-- Grain: product dimension
CREATE OR REPLACE SECURE VIEW VW_DIM_PRODUCT AS
SELECT
    product_sk       AS PRODUCT_SK,
    product_id       AS PRODUCT_ID,
    product_name     AS PRODUCT_NAME,
    product_category AS PRODUCT_CATEGORY,
    brand            AS BRAND
FROM MARTS.DIM_PRODUCT;
