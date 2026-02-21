{% test valid_comarca_coverage_ratio(model) %}

SELECT
    comarca_id,
    year,
    coverage_ratio,
    population_age_65_and_over,
    total_capacit
FROM {{ model }}
WHERE
    coverage_ratio < 0
    OR coverage_ratio > 100
    OR (total_capacit > 0 AND population_age_65_and_over <= 0)

{% endtest %}
