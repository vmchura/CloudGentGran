import * as Plot from "@observablehq/plot";

export function set(input, value) {
  input.value = value;
  input.dispatchEvent(new Event("input", {bubbles: true}));
}

export function plot_catalunya_map_aged_65(width, comarques_boundaries, catalunya_indicator_or_variation,
  comarques_latest_population, comarques_reference_population,
  color_catalunya_map, plot_title) {

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
        fill: (d) => catalunya_indicator_or_variation == "POPULATION_INDICATOR" ? comarques_latest_population[d.properties.comarca_id] :
          (comarques_latest_population[d.properties.comarca_id] - comarques_reference_population[d.properties.comarca_id]),
        title: d => d.properties.comarca_id,
        strokeOpacity: 1.0,
        strokeWidth: 1,
        stroke: "black",
        tip: true
      })
    ]
  });
}

export function plot_catalunya_map_coverage(width, comarques_boundaries,
  ratio_attention_latest_year, plot_title) {

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
        fill: (d) => ratio_attention_latest_year[d.properties.comarca_id],
        title: d => d.properties.comarca_id,
        strokeOpacity: 1.0,
        strokeWidth: 1,
        stroke: "black",
        tip: true
      })
    ]
  });
}
export function plot_catalunya_map_coverage_municipal(width, single_comarque_boundaries,
  ratio_attention_latest_year, municipal_latest_population, catalunya_indicator_type,
  color_catalunya_map, plot_title) {

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
        fill: (d) => catalunya_indicator_type == "POPULATION_INDICATOR" ?  municipal_latest_population[d.properties.municipal_id] : ratio_attention_latest_year[d.properties.municipal_id],
        title: d => d.properties.municipal_id,
        strokeOpacity: 1.0,
        strokeWidth: 1,
        stroke: "black",
        tip: true
      })
    ]
  });
}

export function getColorCatalunyaMap(indicator_type, latest_indicator_average_catalunya_integer, range_colours_indicator) {
  switch(indicator_type) {
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
   default: return {};}
}