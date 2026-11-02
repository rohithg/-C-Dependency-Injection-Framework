-- Synapse serverless external table over Databricks gold Parquet on ADLS
create external data source ads_lakehouse
with ( location = 'https://lake.dfs.core.windows.net/gold' );

create external file format parquet_ff
with ( format_type = parquet );

create external table dbo.usage_daily (
    event_date date,
    region varchar(32),
    segment varchar(16),
    event_type varchar(32),
    event_count bigint,
    bytes_total bigint,
    active_accounts bigint,
    mrr_touched float,
    gb_total float
)
with (
    location = '/usage_daily/',
    data_source = ads_lakehouse,
    file_format = parquet_ff
);
go

create or alter procedure dbo.usp_refresh_usage_daily as
begin
    -- Metadata refresh / stats hint for serverless
    exec sp_refresh_external_table 'dbo.usage_daily';
end;
go
