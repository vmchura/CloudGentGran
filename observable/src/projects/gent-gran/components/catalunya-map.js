import * as Plot from "@observablehq/plot";
import {t} from "./i18n.js";

export function set(input, value) {
  input.value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

export function plot_catalunya_map_aged_65(width, locale_value, comarques_boundaries, catalunya_indicator_or_variation,
  comarques_latest_population, comarques_reference_population,
  color_catalunya_map, plot_title,
  comarca_name_label, current_year, reference_year) {

  return Plot.plot({
    title: plot_title,
    projection: {
      type: "conic-conformal",
      domain: comarques_boundaries
    },
    color: color_catalunya_map,
    width: width,
    marks: [
      Plot.geo(comarques_boundaries, {
        fill: (d) => catalunya_indicator_or_variation == "POPULATION_INDICATOR" ? comarques_latest_population[d.properties.comarca_id]?.elderly_indicator :
          (comarques_latest_population[d.properties.comarca_id]?.elderly_indicator - comarques_reference_population[d.properties.comarca_id]?.elderly_indicator),
        title: d => `${comarca_name_label[d.properties.comarca_id]}
${t(locale_value, "POPULATION")}: ${comarques_latest_population[d.properties.comarca_id]?.population}
${t(locale_value, "POPULATION_65_PLUS")}: ${comarques_latest_population[d.properties.comarca_id]?.population_ge65}
${t(locale_value, "POPULATION_65_PLUS_PERCENTAGE")}: ${comarques_latest_population[d.properties.comarca_id]?.elderly_indicator}
${t(locale_value, "VARIATION_RESPECT_TO", {year: reference_year})}: ${Math.round(comarques_latest_population[d.properties.comarca_id]?.elderly_indicator - comarques_reference_population[d.properties.comarca_id]?.elderly_indicator)}%`,
        strokeOpacity: 1.0,
        strokeWidth: 1,
        stroke: "black",
        tip: true
      })
    ]
  });
}

export function plot_catalunya_map_coverage(width, locale_value, comarques_boundaries,
  ratio_attention_latest_year, plot_title,
  comarca_name_label) {

  return Plot.plot({
    title: plot_title,
    projection: {
      type: "conic-conformal",
      domain: comarques_boundaries
    },
    color: getColorCatalunyaMap("RESIDENCE_COVERAGE", 0, 0),
    width: width,
    marks: [
      Plot.geo(comarques_boundaries, {
        fill: (d) => ratio_attention_latest_year[d.properties.comarca_id]?.coverage_ratio,
        title: d => `${comarca_name_label[d.properties.comarca_id]}
${t(locale_value, "POPULATION_65_PLUS")}: ${ratio_attention_latest_year[d.properties.comarca_id]?.population_ge65}
${t(locale_value, "RESIDENCE_PLACES_ELDERLY")}: ${ratio_attention_latest_year[d.properties.comarca_id]?.total_capacit}
${t(locale_value, "COVERAGE_RATE")}: ${ratio_attention_latest_year[d.properties.comarca_id]?.coverage_ratio}`,
        strokeOpacity: 1.0,
        strokeWidth: 1,
        stroke: "black",
        tip: true
      })
    ]
  });
}
export function plot_catalunya_map_coverage_municipal(width, locale_value, single_comarque_boundaries,
  ratio_attention_latest_year, municipal_latest_population, catalunya_indicator_type,
  color_catalunya_map, plot_title,
  municipal_name_label) {

  return Plot.plot({
    title: plot_title,
    projection: {
      type: "conic-conformal",
      domain: single_comarque_boundaries
    },
    color: color_catalunya_map,
    width: width,
    marks: [
      Plot.geo(single_comarque_boundaries, {
        fill: (d) => catalunya_indicator_type == "POPULATION_INDICATOR" ? municipal_latest_population[d.properties.municipal_id]?.elderly_indicator : ratio_attention_latest_year[d.properties.municipal_id]?.coverage_ratio,
        title: d => `${municipal_name_label[d.properties.municipal_id]}
${t(locale_value, "POPULATION")}: ${municipal_latest_population[d.properties.municipal_id]?.population}
${t(locale_value, "POPULATION_65_PLUS")}: ${municipal_latest_population[d.properties.municipal_id]?.population_ge65}
${t(locale_value, "POPULATION_65_PLUS_PERCENTAGE")}: ${municipal_latest_population[d.properties.municipal_id]?.elderly_indicator}
${t(locale_value, "RESIDENCE_PLACES_ELDERLY")}: ${ratio_attention_latest_year[d.properties.municipal_id]?.total_capacit}
${t(locale_value, "COVERAGE_RATE")}: ${ratio_attention_latest_year[d.properties.municipal_id]?.coverage_ratio}`,
        strokeOpacity: 1.0,
        strokeWidth: 1,
        stroke: "black",
        tip: true
      })
    ]
  });
}

export function getColorCatalunyaMap(indicator_type, latest_indicator_average_catalunya_integer, range_colours_indicator) {
  switch (indicator_type) {
    case "POPULATION_INDICATOR":
      return {
        type: "threshold",
        scheme: "buylrd",
        legend: true,
        pivot: latest_indicator_average_catalunya_integer,
        n: 10,
        unknown: "grey",
        domain: range_colours_indicator,
      };

    case "POPULATION_INDICATOR_VARIATION":
      return {
        type: "diverging",
        scheme: "buylrd",
        legend: true,
        pivot: 0,
        n: 10,
        unknown: "grey"
      };
    case "RESIDENCE_COVERAGE":
      return {
        type: "threshold",
        domain: [3, 4.11, 5, 7],
        scheme: "rdylbu",
        legend: true,
        pivot: 4.11,
        n: 10,
        unknown: "grey",
      };
    default: return {};
  }
}