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

export function plot_trend_population_groups_by_comarca(width, locale_value, comarca_population, nom_comarca, min_year_serveis, max_year_serveis, single_comarca_population) {
  return Plot.plot({
    marginLeft: 50,
    width: width,
    y: {
      grid: true,
      label: single_comarca_population ? t(locale_value, "POPULATION_65_PLUS") : t(locale_value, "POPULATION_65_PLUS_PERCENTAGE"),
    },
    color: {
      domain: single_comarca_population ? ["population_ge65"] : ["elderly_indicator"],
      range: single_comarca_population ? ["#ffd754"] : ["#3b5fc0"],
      legend: false,
      columns: 1,
      rows: 2,
      label: null,
      tickFormat: d => d === "population_ge65" ? t(locale_value, "POPULATION_65_PLUS") : t(locale_value, "POPULATION_65_PLUS_PERCENTAGE")
    },
    x: {
      grid: true,
      tickFormat: d => d.toString(),
      interval: 1,
      label: null,
      domain: [min_year_serveis, max_year_serveis]
    },
    marks: [
      Plot.lineY(comarca_population.params({ comarca_id: nom_comarca.codi_comarca, min_year_serveis: min_year_serveis })
        .filter((row, $) => ((row.comarca_id == $.comarca_id) && (row.year >= $.min_year_serveis))),
        {
          x: "year",
          y: (single_comarca_population ? "population_ge65" : "elderly_indicator"),
          stroke: single_comarca_population ? "#ffd754" : "#3b5fc0",
          strokeWidth: 4
        }),
      Plot.ruleY([0])
    ]
  });
}

export function plot_comarca_by_serveis(width, locale_value, social_services_empty_last_year, nom_comarca, min_year_serveis, max_year_serveis, all_services) {
  return Plot.plot({
    marginLeft: 50,
    width: width,
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
    x: {
      label: null,
      grid: true,
      tickFormat: d => d.toString(),
      domain: [min_year_serveis, max_year_serveis],
      interval: 1
    },
    marks: [
      Plot.lineY(social_services_empty_last_year.params({ comarca_id: nom_comarca.codi_comarca, min_year_serveis: min_year_serveis })
        .filter((row, $) => (row.comarca_id === $.comarca_id)),
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

export function plot_comarca_by_cobertura(width, locale_value, comarca_coverage, nom_comarca, min_year_serveis, max_year_serveis) {
  return Plot.plot({
    marginLeft: 50,
    width: width,
    y: {
      type: "linear",
      grid: true,
      label: t(locale_value, "COVERAGE_RATE"),
    },
    color: {
      legend: false,
      columns: 1,
    },
    x: {
      label: null,
      grid: true,
      tickFormat: d => d.toString(),
      domain: [min_year_serveis, max_year_serveis]
    },
    marks: [
      Plot.lineY(comarca_coverage.params({ comarca_id: nom_comarca.codi_comarca, min_year_serveis: min_year_serveis })
        .filter((row, $) => (row.comarca_id === $.comarca_id)),
        {
          x: "year", y: "coverage_ratio", stroke: "#ff9c38", strokeWidth: 2
        })
    ]
  });
}

export function plot_services_comarca_by_iniciatives(width, locale_value, social_services_empty_last_year, nom_comarca, serveis_selected, min_year_serveis, max_year_serveis) {
  return Plot.plot({
    marginLeft: 50,
    width: width,
    y: {
      type: "linear",
      grid: true,
      label: t(locale_value, "TOTAL_OFFERED_PLACES_ACCUMULATED"),
    },
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
    x: {
      label: null,
      grid: true,
      tickFormat: d => d.toString(),
      domain: [min_year_serveis, max_year_serveis],
      interval: 1
    },
    marks: [
      Plot.areaY(social_services_empty_last_year.params({ comarca_id: nom_comarca.codi_comarca, service_type_id: serveis_selected })
        .filter((row, $) => (row.comarca_id === $.comarca_id) && (row.service_type_id === $.service_type_id))
        .orderby('service_qualification_id', 'year'),
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

export function plot_legend_trend_population(width, locale_value, single_comarca_population) {
  return Plot.legend({
    width: width,
    color: {
      domain: single_comarca_population ? ["population_over_65"] : ["indicator_elderly"],
      range: single_comarca_population ? ["#ffd754"] : ["#3b5fc0"],
      legend: false,
      columns: 1,
      rows: 2,
      label: null,
      tickFormat: d => d === "population_over_65" ? t(locale_value, "POPULATION_65_PLUS") : t(locale_value, "POPULATION_65_PLUS_PERCENTAGE")
    }
  });
}

export function plot_legend_trend_services(width, locale_value, serveis_residence_ratio, all_available_services, service_type) {
  return serveis_residence_ratio ? Plot.legend({
    width: width,
    color: {
      domain: all_available_services.map(row => service_type._data['service_type_description'][service_type._data['service_type_id'].indexOf(row)]),
      range: all_available_services.map(row => colour_by_service.get(row)),
      legend: false,
      columns: 1,
      label: null,
    }
  }) : Plot.legend({
    width: width,
    color: {
      domain: [t(locale_value, "COVERAGE_RATE")],
      range: ["#ff9c38"],
      legend: false,
      columns: 1,
      label: null,
    }
  });
}

export function plot_legend_trend_iniciative(width, locale_value, domain_iniciatives, map_inciative_color, service_qualification) {
  return Plot.legend({
    width: width,
    color: {
      domain: domain_iniciatives.map(row => service_qualification._data['service_qualification_description'][service_qualification._data['service_qualification_id'].indexOf(row)]),
      range: domain_iniciatives.map(row => map_inciative_color.get(row)),
      columns: 1,
      rows: 3,
      label: "Age Groups",
    }
  });
}