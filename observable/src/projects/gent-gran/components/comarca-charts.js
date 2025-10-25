import * as aq from "npm:arquero";
import * as Plot from "@observablehq/plot";
import * as d3 from "d3";

export const service_tag_to_complete = new Map([
  ["Servei de residència assistida", "Servei de residència assistida per a gent gran de caràcter temporal o permanent"],
  ["Servei de centre de dia", "Servei de centre de dia per a gent gran de caràcter temporal o permanent"],
  ["Servei de llar residència", "Servei de llar residència per a gent gran de caràcter temporal o permanent"],
  ["Servei de tutela", "Servei de tutela per a gent gran"],
  ["Servei d' habitatge tutelat", "Servei d' habitatge tutelat per a gent gran de caràcter temporal o permanent"]
]);

export const colour_by_service = new Map([
  ["Servei de centre de dia per a gent gran de caràcter temporal o permanent", "#a160af"],
  ["Servei de residència assistida per a gent gran de caràcter temporal o permanent", "#ff9c38"],
  ["Servei de llar residència per a gent gran de caràcter temporal o permanent", "#f794b9"],
  ["Servei de tutela per a gent gran", "#61b0ff"],
  ["Servei d' habitatge tutelat per a gent gran de caràcter temporal o permanent", "#a87a54"]
]);

export const map_inciative_color = new Map([
  ["Entitat privada d'iniciativa mercantil", "#ed393f"],
  ["Entitat privada d'iniciativa social", "#5ca34b"],
  ["Entitat d'iniciativa pública", "#3b5fc0"]
]);

export function plot_trend_population_groups_by_comarca(width, comarca_population, nom_comarca, min_year_serveis, max_year_serveis, single_comarca_population) {
  return Plot.plot({
    marginLeft: 50,
    width: width,
    y: {
      grid: true,
      label: single_comarca_population ? "Població de 65 anys i més" : "Percentatge de la població de 65 anys i més",
    },
    color: {
      domain: single_comarca_population ? ["population_over_65"] : ["indicator_elderly"],
      range: single_comarca_population ? ["#ffd754"] : ["#3b5fc0"],
      legend: false,
      columns: 1,
      rows: 2,
      label: null,
      tickFormat: d => d === "population_over_65" ? "Població de 65 anys i més" : "Percentatge de la població de 65 anys i més"
    },
    x: {
      grid: true,
      tickFormat: d => d.toString(),
      interval: 1,
      label: null,
      domain: [min_year_serveis, max_year_serveis]
    },
    marks: [
      Plot.lineY(comarca_population.params({comarca_id: nom_comarca.codi_comarca, min_year_serveis: min_year_serveis})
        .filter((row, $) => ((row.comarca_id == $.comarca_id) && (row.year >= $.min_year_serveis))),
        {
          x: "year",
          y: (single_comarca_population ? "population_ge65" : "elderly_indicator"),
          strokeWidth: 4
        }),
      Plot.ruleY([0])
    ]
  });
}

export function plot_comarca_by_serveis(width, social_services_empty_last_year, nom_comarca, min_year_serveis, max_year_serveis) {
  return Plot.plot({
    marginLeft: 50,
    width: width,
    y: {
      type: "linear",
      grid: true,
      label: "Places acumulativa del servei",
    },
    x: {
      label: null,
      grid: true,
      tickFormat: d => d.toString(),
      domain: [min_year_serveis, max_year_serveis],
      interval: 1
    },
    marks: [
      Plot.lineY(social_services_empty_last_year.params({comarca_id: nom_comarca.codi_comarca, min_year_serveis: min_year_serveis})
        .filter((row, $) => (row.comarca_id === $.comarca_id)),
        Plot.mapY(
          "cumsum",
          Plot.groupX(
            { y: d => d3.sum(d, v => v.total_capacit) },
            { x: "year", curve: "step-after", z: "service_type_id", stroke: "service_type_id", tip: true}
          )
        ))
    ]
  });
}

export function plot_comarca_by_cobertura(width, comarca_coverage, nom_comarca, min_year_serveis, max_year_serveis) {
  return Plot.plot({
    marginLeft: 50,
    width: width,
    y: {
      type: "linear",
      grid: true,
      label: "Taxa de cobertura (%)",
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
      Plot.lineY(comarca_coverage.params({comarca_id: nom_comarca.codi_comarca, min_year_serveis: min_year_serveis})
        .filter((row, $) => (row.comarca_id === $.comarca_id)),
        {
          x: "year", y: "coverage_ratio", stroke: "#ff9c38", strokeWidth: 2
        })
    ]
  });
}

export function plot_services_comarca_by_iniciatives(width, social_services_empty_last_year, nom_comarca, serveis_selected, min_year_serveis, max_year_serveis) {
  return Plot.plot({
    marginLeft: 50,
    width: width,
    y: {
      type: "linear",
      grid: true,
      label: "Places acumulativa del servei",
    },
    x: {
      label: null,
      grid: true,
      tickFormat: d => d.toString(),
      domain: [min_year_serveis, max_year_serveis],
      interval: 1
    },
    marks: [
      Plot.areaY(social_services_empty_last_year.params({comarca_id: nom_comarca.codi_comarca, service_type_id: serveis_selected})
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

export function plot_legend_trend_population(width, single_comarca_population) {
  return Plot.legend({
    width: width,
    color: {
      domain: single_comarca_population ? ["population_over_65"] : ["indicator_elderly"],
      range: single_comarca_population ? ["#ffd754"] : ["#3b5fc0"],
      legend: false,
      columns: 1,
      rows: 2,
      label: null,
      tickFormat: d => d === "population_over_65" ? "Població de 65 anys i més" : "Percentatge de la població de 65 anys i més"
    }
  });
}

export function plot_legend_trend_services(width, serveis_residence_ratio, all_available_services, colour_by_service) {
  return serveis_residence_ratio ? Plot.legend({
    width: width,
    color: {
      domain: all_available_services,
      range: all_available_services.map(row => colour_by_service.get(row)),
      legend: false,
      columns: 1,
      label: null,
    }
  }) : Plot.legend({
    width: width,
    color: {
      domain: ["Taxa de cobertura de residència per a gent gran (%)"],
      range: ["#ff9c38"],
      legend: false,
      columns: 1,
      label: null,
    }
  });
}

export function plot_legend_trend_iniciative(width, domain_iniciatives, map_inciative_color) {
  return Plot.legend({
    width: width,
    color: {
      domain: domain_iniciatives,
      range: domain_iniciatives.map(row => map_inciative_color.get(row)),
      columns: 1,
      rows: 3,
      label: "Age Groups",
    }
  });
}