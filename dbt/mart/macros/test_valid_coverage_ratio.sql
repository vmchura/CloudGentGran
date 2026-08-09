{% test valid_coverage_ratio(model) %}

SELECT
    municipal_id,
    year,
    coverage_ratio,
    population_age_65_and_over,
    total_capacit
FROM {{ model }}
WHERE
    coverage_ratio < 0
    OR total_capacit < 0
    OR population_age_65_and_over <= 0

{% endtest %}
