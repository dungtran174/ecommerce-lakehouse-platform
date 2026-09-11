{#
    ==============================================================================
    Modern E-Commerce Data Lakehouse Platform
    dbt Macro: Delta Lake Compaction & Z-ORDER Clustering Procedures
    ==============================================================================

    This macro provides Delta Lake file optimization commands:
    - OPTIMIZE table_name: Compacts small Parquet files into target file sizes
    - ZORDER BY (col1, col2, ...): Co-locates multi-dimensional data along space-filling curves
    - Optional partition filters to limit compaction scope
    - VACUUM table_name RETAIN N HOURS: Purges obsolete historical data files
#}

{% macro optimize_delta_table(relation=none, zorder_by=none, partition_filter=none) -%}
    {#
        Compacts Delta Lake files with optional partition predicate and Z-ORDER clustering.
        Usage:
            {{ optimize_delta_table(this, zorder_by=['order_date', 'customer_id']) }}
    #}
    {%- set tbl = relation if relation is not none else this -%}
    {%- set zorder_cols = none -%}
    {%- if zorder_by is string -%}
        {%- set zorder_cols = zorder_by -%}
    {%- elif zorder_by is iterable and zorder_by is not mapping -%}
        {%- set zorder_cols = zorder_by | join(', ') -%}
    {%- endif -%}

    optimize {{ tbl }}
    {%- if partition_filter %}
    where {{ partition_filter }}
    {%- endif %}
    {%- if zorder_cols %}
    zorder by ({{ zorder_cols }})
    {%- endif %}
{%- endmacro %}

{% macro vacuum_delta_table(relation=none, retain_hours=168) -%}
    {#
        Executes Delta Lake VACUUM to remove obsolete files past the retention threshold.
        Default: 168 hours (7 days).
    #}
    {%- set tbl = relation if relation is not none else this -%}
    vacuum {{ tbl }} retain {{ retain_hours }} hours
{%- endmacro %}

{% macro run_delta_maintenance(relation=none, zorder_by=none, partition_filter=none, retain_hours=168) -%}
    {#
        Convenience macro executing both OPTIMIZE and VACUUM sequentially.
    #}
    {{ optimize_delta_table(relation=relation, zorder_by=zorder_by, partition_filter=partition_filter) }};
    {{ vacuum_delta_table(relation=relation, retain_hours=retain_hours) }}
{%- endmacro %}
