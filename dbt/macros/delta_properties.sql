{#
    ==============================================================================
    Modern E-Commerce Data Lakehouse Platform
    dbt Macro: Delta Lake Table Properties Configuration
    ==============================================================================

    This macro suite configures enterprise Delta Lake table properties for:
    - Auto-Optimization: optimizeWrite (bin-packing files during write operations)
    - Auto-Compaction: autoCompact (merging small files immediately after ingestion)
    - Target file sizes for analytical query performance (default: 128 MB)
    - Retention policies for ACID time travel and VACUUM procedures
#}

{% macro delta_table_properties(optimize_write=true, auto_compact=true, target_file_size_mb=128) -%}
    {# Returns a Python/Jinja dictionary compatible with dbt config(tblproperties=...) #}
    {{ return({
        'delta.autoOptimize.optimizeWrite': 'true' if optimize_write else 'false',
        'delta.autoOptimize.autoCompact': 'true' if auto_compact else 'false',
        'delta.targetFileSize': (target_file_size_mb * 1024 * 1024) | string
    }) }}
{%- endmacro %}

{% macro set_delta_properties(relation=none, optimize_write=true, auto_compact=true, target_file_size_mb=128) -%}
    {#
        Generates an ALTER TABLE SQL statement setting optimizeWrite and autoCompact.
        Can be invoked in a model post_hook or via run-operation.
    #}
    {%- set tbl = relation if relation is not none else this -%}
    alter table {{ tbl }} set tblproperties (
        'delta.autoOptimize.optimizeWrite' = '{{ "true" if optimize_write else "false" }}',
        'delta.autoOptimize.autoCompact' = '{{ "true" if auto_compact else "false" }}',
        'delta.targetFileSize' = '{{ target_file_size_mb * 1024 * 1024 }}'
    )
{%- endmacro %}

{% macro set_delta_retention(relation=none, log_retention_days=30, deleted_file_retention_days=7) -%}
    {#
        Configures log and tombstone retention windows for time travel and VACUUM.
    #}
    {%- set tbl = relation if relation is not none else this -%}
    alter table {{ tbl }} set tblproperties (
        'delta.logRetentionDuration' = 'interval {{ log_retention_days }} days',
        'delta.deletedFileRetentionDuration' = 'interval {{ deleted_file_retention_days }} days'
    )
{%- endmacro %}
