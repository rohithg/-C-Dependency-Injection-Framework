-- =============================================================================
-- COPY INTO RAW landing from internal stage (production-shaped load path)
-- Files are expected as CSV under @retail_dw.raw.stg_retail_inbound/<entity>/
-- matching the seed column headers in seeds/*.csv
-- =============================================================================

create stage if not exists retail_dw.raw.stg_retail_inbound
    directory = (enable = true)
    comment = 'Inbound landing for ERP/CRM/TMS/YMS extracts';

copy into retail_dw.raw.raw_customers
from @retail_dw.raw.stg_retail_inbound/customers/
file_format = (type = csv field_optionally_enclosed_by = '"' skip_header = 1 null_if = ('', 'NULL'))
match_by_column_name = case_insensitive
on_error = 'ABORT_STATEMENT';

copy into retail_dw.raw.raw_products
from @retail_dw.raw.stg_retail_inbound/products/
file_format = (type = csv field_optionally_enclosed_by = '"' skip_header = 1 null_if = ('', 'NULL'))
match_by_column_name = case_insensitive
on_error = 'ABORT_STATEMENT';

copy into retail_dw.raw.raw_orders
from @retail_dw.raw.stg_retail_inbound/orders/
file_format = (type = csv field_optionally_enclosed_by = '"' skip_header = 1 null_if = ('', 'NULL'))
match_by_column_name = case_insensitive
on_error = 'ABORT_STATEMENT';

copy into retail_dw.raw.raw_invoices
from @retail_dw.raw.stg_retail_inbound/invoices/
file_format = (type = csv field_optionally_enclosed_by = '"' skip_header = 1 null_if = ('', 'NULL'))
match_by_column_name = case_insensitive
on_error = 'ABORT_STATEMENT';

copy into retail_dw.raw.raw_shipments
from @retail_dw.raw.stg_retail_inbound/shipments/
file_format = (type = csv field_optionally_enclosed_by = '"' skip_header = 1 null_if = ('', 'NULL'))
match_by_column_name = case_insensitive
on_error = 'ABORT_STATEMENT';

copy into retail_dw.raw.raw_locations
from @retail_dw.raw.stg_retail_inbound/locations/
file_format = (type = csv field_optionally_enclosed_by = '"' skip_header = 1 null_if = ('', 'NULL'))
match_by_column_name = case_insensitive
on_error = 'ABORT_STATEMENT';
