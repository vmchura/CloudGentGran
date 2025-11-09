---
title: Gent-gran
---

```js
const ca_translations = FileAttachment("./projects/gent-gran/locales/ca.json").json();
const es_translations = FileAttachment("./projects/gent-gran/locales/es.json").json();
const en_translations = FileAttachment("./projects/gent-gran/locales/en.json").json();
```
```js
import {t} from "./projects/gent-gran/components/i18n.js";
```
```js
const locale_input = Inputs.select(new Map([['Català', ca_translations],
['Castellano', es_translations],
['English', en_translations]]), {
  value: ca_translations,
  label: t(ca_translations, "LANGUAGE_LABEL")
});
```
```js
const locale_value = Generators.input(locale_input);
```
```js
const social_services_zip_data = FileAttachment("./projects/gent-gran/data/social_services.zip").zip();
const comarques_boundaries = FileAttachment("./projects/gent-gran/data/comarques-1000000.json").json();
const municipals_boundaries = FileAttachment("./projects/gent-gran/data/municipis-1000000.json").json();
  
import {loadData} from "./projects/gent-gran/components/data-loader.js";
import {calculateIndicators} from "./projects/gent-gran/components/indicators.js";
import {build_labels} from "./projects/gent-gran/components/municipal_comarca_labels.js";
import {
    getColorCatalunyaMap,
    plot_catalunya_map_aged_65,
    plot_catalunya_map_coverage,
    plot_catalunya_map_coverage_municipal
} from "./projects/gent-gran/components/catalunya-map.js";

import {
  plot_trend_population_groups_by_comarca,
  plot_comarca_by_serveis,
  plot_comarca_by_cobertura,
  plot_services_comarca_by_iniciatives,
  plot_legend_trend_population,
  plot_legend_trend_services,
  plot_legend_trend_iniciative,
  map_inciative_color
} from "./projects/gent-gran/components/comarca-charts.js";
```
```js
const data = await loadData(social_services_zip_data);
const {
  comarca_population,
  social_services_empty_last_year,
  municipal_coverage,
  comarca_coverage,
  municipal,
  service_type,
  service_qualification,
  population
} = data;
```
```js
const {municipal_name_label, comarca_name_label} = build_labels(municipal);
```
```js
const indicators = calculateIndicators(population, comarca_population, social_services_empty_last_year, comarca_coverage, municipal_coverage);
const {
  all_years,
  census_latest_year,
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
  municipal_latest_population,
  coverage_latest_year
} = indicators;
```
```js
const nom_comarques = municipal.select('nom_comarca').dedupe('nom_comarca').array('nom_comarca');
```
```js
const catalunya_indicator_or_variation_input = Inputs.radio(new Map([
    [t(locale_value, "POPULATION_65_PLUS_PERCENTAGE"), "POPULATION_INDICATOR"],
    [t(locale_value, "PERCENTAGE_VARIATION_YEARS", {referenceYear: reference_year, latestYear: census_latest_year}), "POPULATION_INDICATOR_VARIATION"]]),
    {value: "POPULATION_INDICATOR"});
const catalunya_indicator_or_variation = Generators.input(catalunya_indicator_or_variation_input);
```

```js
const municipal_indicator_type_input = Inputs.radio(new Map([
    [t(locale_value, "RESIDENCE_COVERAGE_RATE"), "RESIDENCE_COVERAGE"],
    [t(locale_value, "POPULATION_65_PLUS_PERCENTAGE"), "POPULATION_INDICATOR"]]),
    {value: "RESIDENCE_COVERAGE"});
const municipal_indicator_type = Generators.input(municipal_indicator_type_input);
```
```js
const all_title_map_by_indicator = new Map([
["POPULATION_INDICATOR", "Percentatge de la població de 65 anys i més"],
["POPULATION_INDICATOR_VARIATION", `Variació percentual de la població de 65 anys i més entre els anys ${reference_year} i ${census_latest_year}`],
["RESIDENCE_COVERAGE", "Porcentatge taxa de cobertura de residència per a gent gran"]]);

const all_sub_title_map_by_indicator = new Map([
["POPULATION_INDICATOR", "Nombre de persones de 65 anys i més dividit pel total de la població."],
["POPULATION_INDICATOR_VARIATION", `Diferència entre el percentatge de població de 65 anys i més l’any ${census_latest_year} i el corresponent a l’any ${reference_year}.`],
["RESIDENCE_COVERAGE", "La taxa de cobertura de s'obté a partir del quocient entre el total de població de 65 anys i més i el total oferta de places. S'expressa en tant per cent."]]);
```
```js
const title_map_by_indicator = all_title_map_by_indicator.get(catalunya_indicator_or_variation);
const sub_title_map_by_indicator = all_sub_title_map_by_indicator.get(catalunya_indicator_or_variation);
```
```js
const color_catalunya_map = getColorCatalunyaMap(catalunya_indicator_or_variation, latest_indicator_average_catalunya_integer, range_colours_indicator);
```
```js
const color_municipal_map = getColorCatalunyaMap(municipal_indicator_type, latest_indicator_average_catalunya_integer, range_colours_indicator);
```
```js
const nom_comarca_input = Inputs.select(municipal.select('nom_comarca', 'codi_comarca').dedupe('nom_comarca', 'codi_comarca').orderby('nom_comarca'), {label: t(locale_value, "COMARCA_LABEL") + ": ", format: x => x.nom_comarca, unique: true})
const nom_comarca = Generators.input(nom_comarca_input);
```
```js
const all_year_serveis_selected = social_services_empty_last_year.params({codi_comarca: nom_comarca.codi_comarca}).filter((d, $) => d.comarca_id == $.codi_comarca).select('year').array('year');
const max_year_serveis = Math.max(...all_year_serveis_selected);
const min_year_serveis = Math.min(...all_year_serveis_selected);
```
```js
const single_comarca_population_input = Inputs.radio(new Map([[t(locale_value, "TREND_POPULATION_65_PLUS"), true],
        [t(locale_value, "TREND_INDICATOR_POPULATION_65_PLUS"), false]]),
    {value: true, label: null});
const single_comarca_population = Generators.input(single_comarca_population_input);
```
```js
const serveis_residence_ratio_input = Inputs.radio(new Map([[t(locale_value, "ALL_SERVICES"), true], [t(locale_value, "RESIDENCE_COVERAGE_RATE"), false]]),
    {value: true, label: null});
const serveis_residence_ratio = Generators.input(serveis_residence_ratio_input)
```
```js
const social_services_comarca = social_services_empty_last_year.params({comarca_id: nom_comarca.codi_comarca}).filter((row, $) => (row.comarca_id === $.comarca_id));
const all_available_services = social_services_comarca.filter(row =>  row.total_capacit > 0).select('service_type_id').dedupe('service_type_id').array('service_type_id');
```
```js
const serveis_input = Inputs.select(new Map(all_available_services.map(s => [service_type._data['service_type_description'][service_type._data['service_type_id'].indexOf(s)], s])), {
    value: [all_available_services[0]],
    label: t(locale_value, "SERVICE_LABEL")
})
const serveis_selected = Generators.input(serveis_input)
```
```js
const serveis_by_iniciative = social_services_comarca.params({service_type_id: serveis_selected}).filter((row, $) => (row.service_type_id === $.service_type_id))
```
```js
const domain_iniciatives = serveis_by_iniciative.select('service_qualification_id').dedupe('service_qualification_id').array('service_qualification_id');
```
```js
const comarca_name_for_distrit_input = Inputs.select(municipal.select('nom_comarca', 'codi_comarca').dedupe('nom_comarca', 'codi_comarca').orderby('nom_comarca'), {label: t(locale_value, "COMARCA_LABEL") + ": ", format: x => x.nom_comarca, unique: true, value: "01"})
const comarca_code_for_distrit_value = Generators.input(comarca_name_for_distrit_input);
```
```js
const valid_municipal_codes = municipal.params({codi_comarca: comarca_code_for_distrit_value.codi_comarca}).filter((d, $) => d.codi_comarca === $.codi_comarca).array("codi");
const single_comarca_map = {
  ...municipals_boundaries,
  features: municipals_boundaries.features.filter(
    f => valid_municipal_codes.includes(f.properties.municipal_id )
  )
};
```
```js
const municipal_plot = plot_catalunya_map_coverage_municipal(500, locale_value, single_comarca_map,
ratio_attention_municipal_latest_year, municipal_latest_population, municipal_indicator_type,
color_municipal_map, all_title_map_by_indicator.get(municipal_indicator_type),
municipal_name_label);
```
# ${t(locale_value, "TITLE")} (${coverage_latest_year})

<div>${locale_input}</div>

<div class="story-section">
  <p>
    ${t(locale_value, "INTRO_TEXT")}
  </p>
</div>

---

<div class="story-section">
    <h2>${t(locale_value, "WHERE_ELDERLY_LIVE")}</h2>
    <p>
    ${t(locale_value, "WHERE_ELDERLY_LIVE_DESC")}
    </p>
    ${catalunya_indicator_or_variation_input}

<div class="grid grid-cols-3">
    <div class="grid-colspan-2">
        <figure class="grafic" style="max-width: none;">
            ${resize((width) => plot_catalunya_map_aged_65(width, locale_value, comarques_boundaries, catalunya_indicator_or_variation, 
              comarques_latest_population, comarques_reference_population, 
              color_catalunya_map, title_map_by_indicator,
              comarca_name_label, census_latest_year, reference_year))}
        </figure>
<div class="note">
    <bold>${title_map_by_indicator}</bold>: ${sub_title_map_by_indicator}
</div>
    </div>
    <div class="grid-colspan-1">
        <h2>${t(locale_value, "CATALONIA")} ${census_latest_year}</h2>
        <div class="grid-colspan-1">
            <div class="card">
                <h4>${t(locale_value, "POPULATION_65_PLUS")}</h4>
                <span class="big">${Number(gent_gran_population_latest_year).toLocaleString('ca-ES')}</span>
            </div>  
            <div class="card">
                <h4>${t(locale_value, "POPULATION_65_PLUS_PERCENTAGE")}</h4>
                <span class="big">${Number(latest_indicator_average_catalunya).toLocaleString('ca-ES')}%</span>
            </div>
            <div class="card">
                <h4>${t(locale_value, "VARIATION_RESPECT_TO", {year: reference_year})}</h4>
                <span class="big">${sign_difference_reference}${Number(latest_indicator_average_catalunya - reference_year_indicator_average_catalunya).toLocaleString('ca-ES')}%</span>
            </div>
        </div>
    </div>
</div>
</div>

---

<div class="story-section">
  <h2>${t(locale_value, "RESIDENTIAL_PLACES_SUFFICIENCY")}</h2>
  <p>
    ${t(locale_value, "ACCORDING_TO")}<a href="https://www.acra.cat/estudio-socioecon%C3%B3mico-de-la-atenci%C3%B3n-para-personas-en-situaci%C3%B3n-de-dependencia-en-espa%C3%B1a-informe-final_1123083.pdf">Estudio socioeconómico de la atención para personas en situación de dependencia en España</a>, ${t(locale_value, "REFERENCE_RATIO_DESC")} 
${t(locale_value, "TERRITORY_ANALYSIS_DESC")}
  </p>

  <div class="grid grid-cols-3">
    <div class="grid-colspan-2">
        <figure class="grafic" style="max-width: none;">
            ${resize((width) => plot_catalunya_map_coverage(width, locale_value, comarques_boundaries, 
              ratio_attention_latest_year, t(locale_value, "RESIDENCE_COVERAGE_PERCENTAGE"),
              comarca_name_label))}
        </figure>
        <div class="note">
        ${t(locale_value, "COVERAGE_RATE_DESC")}
        </div>
    </div>
    <div class="grid-colspan-1">
      <h2>${t(locale_value, "CATALONIA")} ${coverage_latest_year}</h2>
      <div class="card">
          <h4>${t(locale_value, "RESIDENCE_PLACES_ELDERLY")}</h4>
          <span class="big">${Number(number_places_residence).toLocaleString('ca-ES')}</span>
      </div>
      <div class="card">
          <h4>${t(locale_value, "COVERAGE_RATE")}</h4>
          <span class="big">${Number(catalunya_ratio_cobertura).toLocaleString('ca-ES')}%</span>
      </div>
      <div class="card">
          <h4>${deficit_camas_residencia < 0? t(locale_value, "SURPLUS_PLACES") : t(locale_value, "DEFICIT_PLACES")}</h4>
          <span class="big">${Number(deficit_camas_residencia).toLocaleString('ca-ES')}</span>
      </div>
    </div>
  </div>
</div>

---

<div class="story-section">
  <h2>${t(locale_value, "EVOLUTION_POPULATION_SERVICES")}</h2>
  <p>
    ${t(locale_value, "EVOLUTION_DESC")}
    ${t(locale_value, "TEMPORAL_ANALYSIS_DESC")}
  </p>

  <div class="grid grid-cols-3">
      <h3 class="grid-colspan-1">${t(locale_value, "TREND_POPULATION_SERVICES_COMARCA")}</h3>
      <div class="grid-colspan-1" style="align-self: center;">
          ${nom_comarca_input}
      </div>
  </div>

  <div class="grid grid-cols-3">
      <div class="card grid-colspan-1">
          <h4>${t(locale_value, "EVOLUTION_POPULATION_65_PLUS")}</h4>
          ${single_comarca_population_input}
          ${resize((width) => plot_legend_trend_population(width, locale_value, single_comarca_population))}
          <figure>${resize((width) => plot_trend_population_groups_by_comarca(width, locale_value, comarca_population, nom_comarca, min_year_serveis, max_year_serveis, single_comarca_population))}</figure>
      </div>
      <div class="card grid-colspan-1">
          <h4>${t(locale_value, "ASSISTANCE_SERVICES")}</h4>
          ${serveis_residence_ratio_input}
          ${resize((width) => plot_legend_trend_services(width, locale_value, serveis_residence_ratio, all_available_services, service_type))}
          <figure>${resize((width) => serveis_residence_ratio ? plot_comarca_by_serveis(width, locale_value, social_services_empty_last_year, nom_comarca, min_year_serveis, max_year_serveis, all_available_services) : plot_comarca_by_cobertura(width, locale_value, comarca_coverage, nom_comarca, min_year_serveis, max_year_serveis))}</figure>
      </div>
      <div class="card grid-colspan-1">
          <h4>${t(locale_value, "SERVICE_QUALIFICATION")}</h4>
          ${serveis_input}
          ${resize((width) => plot_legend_trend_iniciative(width, plot_legend_trend_services, domain_iniciatives, map_inciative_color, service_qualification))} 
          <figure>${resize((width) => plot_services_comarca_by_iniciatives(width, locale_value, social_services_empty_last_year, nom_comarca, serveis_selected, min_year_serveis, max_year_serveis, all_available_services))}</figure>
      </div>
  </div>

</div>

---

<div class="story-section">
  <h2>Detall territorial per comarca</h2>
  <p>
    ${t(locale_value, "TERRITORIAL_DETAIL_DESC")}
  </p>
  <p>
  ${t(locale_value, "NO_DATA_MUNICIPALITIES")}
</p>
  ${comarca_name_for_distrit_input} 
  ${municipal_indicator_type_input}
  <div class="grid grid-cols-3">
    <div class="grid-colspan-2">
        <fig>${municipal_plot}</fig>
        <div class="note">
            <bold>${all_title_map_by_indicator.get(municipal_indicator_type)}</bold>: ${all_sub_title_map_by_indicator.get(municipal_indicator_type)}
        <br/>
            ${t(locale_value, "GREY_AREAS_NOTE")}
        </div>
    </div>
    <div class="grid-colspan-1">
        <h2>${comarca_code_for_distrit_value.nom_comarca} ${coverage_latest_year}</h2>
        <div class="card">
            <h4>${t(locale_value, "POPULATION_65_PLUS")}</h4>
            <span class="big">${Number(comarques_latest_population[comarca_code_for_distrit_value.codi_comarca]?.population_ge65).toLocaleString('ca-ES')}</span>
        </div>  
        <div class="card">
            <h4>${t(locale_value, "POPULATION_65_PLUS_PERCENTAGE")}</h4>
            <span class="big">${Number(comarques_latest_population[comarca_code_for_distrit_value.codi_comarca]?.elderly_indicator).toLocaleString('ca-ES')}%</span>
        </div>
        <div class="card">
          <h4>${t(locale_value, "RESIDENCE_PLACES_ELDERLY")}</h4>
          <span class="big">${Number(ratio_attention_latest_year[comarca_code_for_distrit_value.codi_comarca]?.total_capacit).toLocaleString('ca-ES')}</span>
        </div>
        <div class="card">
            <h4>${t(locale_value, "COVERAGE_RATE")}</h4>
            <span class="big">${Number(ratio_attention_latest_year[comarca_code_for_distrit_value.codi_comarca]?.coverage_ratio).toLocaleString('ca-ES')}%</span>
        </div>
        <div class="card">
            <h4>${ratio_attention_latest_year[comarca_code_for_distrit_value.codi_comarca]?.deficit_411 < 0 ? t(locale_value, "SURPLUS_PLACES") : t(locale_value, "DEFICIT_PLACES")}</h4>
            <span class="big">${Number(Math.abs(ratio_attention_latest_year[comarca_code_for_distrit_value.codi_comarca]?.deficit_411)).toLocaleString('ca-ES')}</span>
        </div>
    </div>
  </div>
</div>

---

## ${t(locale_value, "SOURCES")}

* [${t(locale_value, "SOURCE_ENTITIES_TITLE")}](https://analisi.transparenciacatalunya.cat/ca/Societat-benestar/Registre-d-entitats-serveis-i-establiments-socials/ivft-vegh/about_data): 
${t(locale_value, "SOURCE_ENTITIES_DESCRIPTION")}

* [${t(locale_value, "SOURCE_POPULATION_TITLE")}](https://www.idescat.cat/pub/?id=censph): ${t(locale_value, "SOURCE_POPULATION_DESCRIPTION")}

* [${t(locale_value, "SOURCE_BOUNDARIES_TITLE")}](https://www.icgc.cat/en/Geoinformation-and-Maps/Data-and-products/Cartographic-geoinformation/Administrative-boundaries): ${t(locale_value, "SOURCE_BOUNDARIES_DESCRIPTION")}

---

```js
const content = {
  "ca": [`Els comentaris, recomanacions i retroalimentació constructiva són benvinguts. Podeu contactar-me directament a través de LinkedIn per compartir les vostres perspectives o suggeriments per a futurs estudis.
Tot el codi font és obert i està disponible en un únic repositori de GitHub.`],
  "en": [`Comments, recommendations, and constructive feedback are welcome. You may contact me directly via LinkedIn to share your insights or suggestions for future studies.
All source code is open and available in a single GitHub repository`],
  "es": [`Se agradecen comentarios, recomendaciones y retroalimentación constructiva. Puede contactarme directamente a través de LinkedIn para compartir sus perspectivas o sugerencias para futuros estudios.
Todo el código fuente es abierto y está disponible en un único repositorio de GitHub.`]}[locale_value['BASE']] || "ERROR";
```

<div class="about-this">
<p>${content[0]}</p>
</div>
<section id="contact" aria-labelledby="contact-heading" style="font-family:system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial; max-width:720px; margin:32px auto; padding:16px;">
  <div style="display:flex; gap:12px; flex-wrap:wrap;">
    <!-- LinkedIn -->
    <a
      href="https://www.linkedin.com/in/victor-chura/"
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Contact me"
      style="display:flex; align-items:center; gap:10px; text-decoration:none; padding:10px 14px; border-radius:10px; border:1px solid #e6e6e6; background:#fff; box-shadow:0 1px 2px rgba(0,0,0,0.03); min-width:220px;"
    >
      <!-- LinkedIn SVG -->
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
        <rect x="2" y="2" width="20" height="20" rx="3" fill="#0077B5"></rect>
        <path d="M6.94 9.5H4.75V19H6.94V9.5ZM5.85 8.35C6.518 8.35 7.05 7.82 7.05 7.15C7.05 6.48 6.518 5.95 5.85 5.95C5.182 5.95 4.65 6.48 4.65 7.15C4.65 7.82 5.182 8.35 5.85 8.35Z" fill="white"></path>
        <path d="M9.5 9.5H11.61V10.86H11.65C12.106 10.1 13.062 9.25 14.63 9.25C17.28 9.25 18 11.02 18 13.44V19H15.81V13.9C15.81 12.58 15.78 10.81 14.07 10.81C12.34 10.81 12.05 12.26 12.05 13.82V19H9.86V9.5H9.5Z" fill="white"></path>
      </svg>
      <div style="text-align:left;">
        <div style="font-weight:600; color:#0b2b3b;">Victor Chura</div>
        <div style="font-size:0.88rem; color:#556565;">LinkedIn</div>
      </div>
    </a>
    <!-- GitHub -->
    <a
      href="https://github.com/vmchura/CloudGentGran"
      target="_blank"
      rel="noopener noreferrer"
      aria-label="All the source code"
      style="display:flex; align-items:center; gap:10px; text-decoration:none; padding:10px 14px; border-radius:10px; border:1px solid #e6e6e6; background:#fff; box-shadow:0 1px 2px rgba(0,0,0,0.03); min-width:220px;"
    >
      <!-- GitHub SVG -->
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
        <rect x="2" y="2" width="20" height="20" rx="3" fill="#111"></rect>
        <path fill-rule="evenodd" clip-rule="evenodd" d="M12 .5C5.648.5.5 5.648.5 12c0 5.088 3.292 9.402 7.865 10.936.575.105.78-.25.78-.556 0-.275-.01-1.003-.015-1.97-3.2.696-3.877-1.544-3.877-1.544-.522-1.328-1.275-1.682-1.275-1.682-1.042-.712.08-.698.08-.698 1.15.081 1.755 1.181 1.755 1.181 1.025 1.754 2.688 1.248 3.344.954.103-.743.4-1.248.726-1.535-2.554-.291-5.244-1.277-5.244-5.68 0-1.254.448-2.279 1.183-3.083-.119-.292-.513-1.467.113-3.057 0 0 .964-.309 3.16 1.178.916-.255 1.9-.382 2.878-.387.978.005 1.963.132 2.882.387 2.195-1.487 3.157-1.178 3.157-1.178.628 1.59.234 2.765.115 3.057.737.804 1.183 1.829 1.183 3.083 0 4.415-2.695 5.386-5.258 5.668.411.354.777 1.053.777 2.122 0 1.532-.014 2.767-.014 3.146 0 .31.203.668.787.554C20.71 21.398 24 17.088 24 12 24 5.648 18.352.5 12 .5z" fill="#fff"/>
      </svg>
      <div style="text-align:left;">
        <div style="font-weight:600; color:#0b2b3b;">CloudGentGran</div>
        <div style="font-size:0.88rem; color:#556565;">GitHub</div>
      </div>
    </a>
  </div>
</section>

<style>
.story-section { margin-bottom: 3rem; }
</style>