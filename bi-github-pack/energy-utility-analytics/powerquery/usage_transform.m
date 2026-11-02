// Power Query (M) — resume: Power Query ETL for energy program extracts
let
    Source = Csv.Document(File.Contents("seeds/fct_energy_usage.csv"),[Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.None]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted,{
        {"usage_id", type text}, {"utility_id", type text}, {"program_id", type text},
        {"usage_date", type date}, {"kwh", type number}, {"peak_kw", type number},
        {"customer_count", Int64.Type}, {"incentive_paid_usd", type number},
        {"compliance_flag", type text}}),
    IsCompliant = Table.AddColumn(Typed, "IsCompliant", each [compliance_flag] = "Y", type logical),
    Filtered = Table.SelectRows(IsCompliant, each [kwh] > 0)
in
    Filtered
