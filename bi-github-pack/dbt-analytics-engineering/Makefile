.PHONY: deps seed run test build docs parse clean

deps:
	dbt deps

seed:
	dbt seed

run:
	dbt run

test:
	dbt test

build:
	dbt build

parse:
	dbt parse

docs:
	dbt docs generate
	dbt docs serve

clean:
	dbt clean
	rm -f target/*.duckdb target/*.duckdb.wal
