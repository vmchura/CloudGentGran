import * as aq from "npm:arquero";

export function calculateIndicators(population, comarca_population, social_services_empty_last_year, comarca_coverage, municipal_coverage) {
  const all_years = comarca_population.dedupe('year').array('year');
  const latest_year = Math.max(...all_years);

  const population_latest_year = comarca_population
    .params({ latest_year })
    .filter((d, $) => d.year == $.latest_year);

  const total_population_latest_year = population_latest_year
    .rollup({ total: d => aq.op.sum(d.population) })
    .get('total', 0);

  const gent_gran_population_latest_year = population_latest_year
    .rollup({ total: d => aq.op.sum(d.population_ge65) })
    .get('total', 0);

  const latest_indicator_average_catalunya = Math.round(gent_gran_population_latest_year * 1000 / total_population_latest_year) / 10.0;
  const latest_indicator_average_catalunya_integer = Math.round(latest_indicator_average_catalunya);
  const range_colours_indicator = [...Array(8).keys()].map(i => latest_indicator_average_catalunya_integer - 7 + i * 2);

  const reference_year = all_years.reduce((closest, year) =>
    Math.abs(year - 2000) < Math.abs(closest - 2000) ? year : closest
  );

  const population_reference_year = comarca_population
    .params({ reference_year })
    .filter((d, $) => d.year == $.reference_year);

  const total_population_reference_year = population_reference_year
    .rollup({ total: d => aq.op.sum(d.population) })
    .get('total', 0);

  const gent_gran_population_reference_year = population_reference_year
    .rollup({ total: d => aq.op.sum(d.population_ge65) })
    .get('total', 0);

  const reference_year_indicator_average_catalunya = Math.round(gent_gran_population_reference_year * 1000 / total_population_reference_year) / 10.0;

  const sign_difference_reference = (latest_indicator_average_catalunya_integer > reference_year_indicator_average_catalunya) ? "+" : "";

  const number_places_residence = social_services_empty_last_year.filter(row => row.service_type_id == 'RES-003')
    .rollup({ total: d => aq.op.sum(d.total_capacit) })
    .get('total', 0);

  const catalunya_ratio_cobertura = Math.round(1000 * number_places_residence / gent_gran_population_latest_year) / 10.0;
  const deficit_camas_residencia = Math.round(0.0411 * gent_gran_population_latest_year - number_places_residence);
  const deficit_superavit = deficit_camas_residencia > 0 ? "Dèficit" : "Superàvit";

  const ratio_attention_latest_year = Object.fromEntries(
    comarca_coverage.params({latest_year: latest_year})
      .filter(d => d.year === latest_year)
      .objects()
      .map(d => [d.comarca_id, d.coverage_ratio])
  );
  const ratio_attention_municipal_latest_year = Object.fromEntries(
      municipal_coverage.params({latest_year: latest_year})
        .filter(d => d.year === latest_year)
        .objects()
        .map(d => [d.municipal_id, d.coverage_ratio])
    );

  const comarques_latest_population = Object.fromEntries(
    comarca_population.params({latest_year: latest_year})
      .filter((d, $) => d.year === $.latest_year)
      .select("comarca_id", "population_ge65", "population")
      .objects()
      .map(d => [
        d.comarca_id,
        Math.round((d.population_ge65 * 1000.0) / d.population) / 10.0
      ])
  );

  const municipal_latest_population = Object.fromEntries(
    population.params({latest_year: latest_year})
      .filter((d, $) => d.year === $.latest_year)
      .select("municipal_code", "population_ge65", "population")
      .objects()
      .map(d => [
        d.municipal_code,
        Math.round((d.population_ge65 * 1000.0) / d.population) / 10.0
      ])
  );

  const comarques_reference_population = Object.fromEntries(
    comarca_population.params({reference_year: reference_year})
      .filter((d, $) => d.year === $.reference_year)
      .select("comarca_id", "population_ge65", "population")
      .objects()
      .map(d => [
        d.comarca_id,
        Math.round((d.population_ge65 * 1000.0) / d.population) / 10.0
      ])
  );

  return {
    all_years,
    latest_year,
    reference_year,
    latest_indicator_average_catalunya,
    latest_indicator_average_catalunya_integer,
    reference_year_indicator_average_catalunya,
    range_colours_indicator,
    sign_difference_reference,
    total_population_latest_year,
    gent_gran_population_latest_year,
    total_population_reference_year,
    gent_gran_population_reference_year,
    number_places_residence,
    catalunya_ratio_cobertura,
    deficit_camas_residencia,
    deficit_superavit,
    ratio_attention_latest_year,
    comarques_latest_population,
    comarques_reference_population,
    ratio_attention_municipal_latest_year,
    municipal_latest_population
  };
}