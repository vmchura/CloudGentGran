import * as aq from "npm:arquero";
import * as Plot from "@observablehq/plot";
import * as d3 from "d3";
import {t} from "./i18n.js";

export const colour_by_service = new Map([
  ["DAY-001", "#a160af"],
  ["RES-003", "#ff9c38"],
  ["RES-002", "#f794b9"],
  ["TUT-001", "#61b0ff"],
  ["RES-001", "#a87a54"]
]);

export const map_inciative_color = new Map([
  ["PRV-001", "#ed393f"],
  ["PRV-002", "#5ca34b"],
  ["PUB-001", "#3b5fc0"]
]);

const createTimeSeriesXAxis = (min_year_serveis, max_year_serveis) => ({
  label: null,
  grid: true,
  tickFormat: d => d.toString(),
  domain: [min_year_serveis, max_year_serveis],
  interval: 1
});

const createBaseChartConfig = (width) => ({
  marginLeft: 50,
  width: width
});

const createLinearYAxis = (label, locale_value) => ({
  type: "linear",
  grid: true,
  label: t(locale_value, label)
});

const createColorLegend = (width, domain, range, options = {}) => ({
  width,
  color: {
    domain,
    range,
    legend: false,
    columns: 1,
    label: null,
    ...options
  }
});

const createPopulationLegend = (width, locale_value, showAbsolute) => ({
  width,
  color: {
    domain: showAbsolute ? ["population_age_65_and_over"] : ["elderly_indicator"],
    range: showAbsolute ? ["#ffd754"] : ["#3b5fc0"],
    legend: false,
    columns: 1,
    rows: 2,
    label: null,
    tickFormat: d => d === "population_age_65_and_over" ? t(locale_value, "POPULATION_65_PLUS") : t(locale_value, "POPULATION_65_PLUS_PERCENTAGE")
  }
});

const createServicesLegend = (width, locale_value, all_available_services, serviceTypeLabel) => 
  createColorLegend(width, 
    all_available_services.map(row => serviceTypeLabel.get(row)),
    all_available_services.map(row => colour_by_service.get(row))
  );

const createCoverageLegend = (width, locale_value) =>
  createColorLegend(width, 
    [t(locale_value, "COVERAGE_RATE")],
    ["#ff9c38"]
  );

const createInitiativesLegend = (width, locale_value, domain_iniciatives, map_inciative_color, serviceQualificationLabel) => ({
  width,
  color: {
    domain: (domain_iniciatives || []).map(id => serviceQualificationLabel.get(id)),
    range: (domain_iniciatives || []).map(id => map_inciative_color.get(id)),
    columns: 1,
    rows: 3,
    label: "Age Groups"
  }
});

export async function plot_trend_population_groups_by_comarca(width, locale_value, db, comarca_name, min_year_serveis, max_year_serveis, single_comarca_population) {
  const comarcaPopulationPlot = await db.sql`
  SELECT 
    year,
    population_age_65_and_over,
    elderly_indicator
  FROM social_services.comarca_population
  WHERE comarca_id = ${comarca_name.comarca_id}
    AND year >= ${min_year_serveis}
  ORDER BY year
`;

  return Plot.plot({
    ...createBaseChartConfig(width),
    y: {
      grid: true,
      label: single_comarca_population ? t(locale_value, "POPULATION_65_PLUS") : t(locale_value, "POPULATION_65_PLUS_PERCENTAGE"),
    },
    color: {
      domain: single_comarca_population ? ["population_age_65_and_over"] : ["elderly_indicator"],
      range: single_comarca_population ? ["#ffd754"] : ["#3b5fc0"],
      legend: false,
      columns: 1,
      rows: 2,
      label: null,
      tickFormat: d => d === "population_age_65_and_over" ? t(locale_value, "POPULATION_65_PLUS") : t(locale_value, "POPULATION_65_PLUS_PERCENTAGE")
    },
    x: createTimeSeriesXAxis(min_year_serveis, max_year_serveis),
    marks: [
      Plot.lineY(comarcaPopulationPlot,
        {
          x: "year",
          y: (single_comarca_population ? "population_age_65_and_over" : "elderly_indicator"),
          stroke: single_comarca_population ? "#ffd754" : "#3b5fc0",
          strokeWidth: 4
        }),
      Plot.ruleY([0])
    ]
  });
}

export async function plot_comarca_by_serveis(width, locale_value, db, comarca_name, min_year_serveis, max_year_serveis, all_services) {
  const servicesData = await db.sql`
    SELECT 
      year,
      service_type_id,
      total_capacit
    FROM social_services.social_services_empty_last_year
    WHERE comarca_id = ${comarca_name.comarca_id}
      AND year >= ${min_year_serveis}
    ORDER BY year, service_type_id
  `;

  return Plot.plot({
    ...createBaseChartConfig(width),
    y: {
      type: "linear",
      grid: true,
      label: t(locale_value, "TOTAL_OFFERED_PLACES_ACCUMULATED"),
    },
    color: {
      domain: all_services,
      range: all_services.map(row => colour_by_service.get(row)),
      legend: false,
      columns: 1,
      label: "Age Groups",
    },
    x: createTimeSeriesXAxis(min_year_serveis, max_year_serveis),
    marks: [
      Plot.lineY(servicesData,
        Plot.mapY(
          "cumsum",
          Plot.groupX(
            { y: d => d3.sum(d, v => v.total_capacit) },
            { x: "year", curve: "step-after", z: "service_type_id", stroke: "service_type_id", tip: true }
          )
        ))
    ]
  });
}

export async function plot_comarca_by_cobertura(width, locale_value, db, comarca_name, min_year_serveis, max_year_serveis) {
  const coverageData = await db.sql`
    SELECT 
      year,
      coverage_ratio
    FROM social_services.comarca_coverage
    WHERE comarca_id = ${comarca_name.comarca_id}
      AND year >= ${min_year_serveis}
    ORDER BY year
  `;

  return Plot.plot({
    ...createBaseChartConfig(width),
    y: createLinearYAxis("COVERAGE_RATE", locale_value),
    color: {
      legend: false,
      columns: 1,
    },
    x: createTimeSeriesXAxis(min_year_serveis, max_year_serveis),
    marks: [
      Plot.lineY(coverageData,
        {
          x: "year", y: "coverage_ratio", stroke: "#ff9c38", strokeWidth: 2
        })
    ]
  });
}

export async function plot_services_comarca_by_iniciatives(width, locale_value, db, comarca_name, serveis_selected, min_year_serveis, max_year_serveis) {
  const initiativesData = await db.sql`
    SELECT 
      year,
      service_qualification_id,
      total_capacit
    FROM social_services.social_services_empty_last_year
    WHERE comarca_id = ${comarca_name.comarca_id}
      AND service_type_id = ${serveis_selected}
    ORDER BY service_qualification_id, year
  `;

  return Plot.plot({
    ...createBaseChartConfig(width),
    y: createLinearYAxis("TOTAL_OFFERED_PLACES_ACCUMULATED", locale_value),
    color: {
      domain: [
        "PRV-001",
        "PRV-002",
        "PUB-001"],
      range: ["#ed393f", "#5ca34b", "#3b5fc0"],
      legend: false,
      columns: 1,
      rows: 3,
      label: "Age Groups",
    },
    x: createTimeSeriesXAxis(min_year_serveis, max_year_serveis),
    marks: [
      Plot.areaY(initiativesData,
        Plot.mapY(
          "cumsum",
          Plot.groupX(
            { y: d => d3.sum(d, v => v.total_capacit) },
            {
              x: "year",
              curve: "step-after",
              fill: "service_qualification_id",
              stroke: "service_qualification_id",
              tip: true
            }
          )
        ))
    ]
  });
}

export const plot_legend_trend_population = createPopulationLegend;

export const plot_legend_trend_services = (width, locale_value, serveis_residence_ratio, all_available_services, serviceTypeLabel) => 
  serveis_residence_ratio 
    ? createServicesLegend(width, locale_value, all_available_services, serviceTypeLabel)
    : createCoverageLegend(width, locale_value);

export const plot_legend_trend_iniciative = createInitiativesLegend;
