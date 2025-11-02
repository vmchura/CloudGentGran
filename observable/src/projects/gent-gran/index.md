```js
const social_services_zip_data = FileAttachment("./data/social_services.zip").zip();
const comarques_boundaries = FileAttachment("./data/comarques-1000000.json").json();
const municipals_boundaries = FileAttachment("./data/municipis-1000000.json").json();
  
import {loadData} from "./components/data-loader.js";
import {calculateIndicators} from "./components/indicators.js";
import {build_labels} from "./components/municipal_comarca_labels.js";
import {
    getColorCatalunyaMap,
    plot_catalunya_map_aged_65,
    plot_catalunya_map_coverage,
    plot_catalunya_map_coverage_municipal
} from "./components/catalunya-map.js";

import {
  plot_trend_population_groups_by_comarca,
  plot_comarca_by_serveis,
  plot_comarca_by_cobertura,
  plot_services_comarca_by_iniciatives,
  plot_legend_trend_population,
  plot_legend_trend_services,
  plot_legend_trend_iniciative,
  service_tag_to_complete,
  map_inciative_color
} from "./components/comarca-charts.js";
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
} = indicators;
```
```js
const nom_comarques = municipal.select('nom_comarca').dedupe('nom_comarca').array('nom_comarca');
```
```js
const catalunya_indicator_or_variation_input = Inputs.radio(new Map([
    ["Percentatge de la població de 65 anys i més", "POPULATION_INDICATOR"],
    [`Variació percentual entre els anys ${reference_year} i ${latest_year}`, "POPULATION_INDICATOR_VARIATION"]]),
    {value: "POPULATION_INDICATOR"});
const catalunya_indicator_or_variation = Generators.input(catalunya_indicator_or_variation_input);
```

```js
const municipal_indicator_type_input = Inputs.radio(new Map([
    [`Taxa de cobertura de residència per a gent gran`, "RESIDENCE_COVERAGE"],
    ["Percentatge de la població de 65 anys i més", "POPULATION_INDICATOR"]]),
    {value: "RESIDENCE_COVERAGE"});
const municipal_indicator_type = Generators.input(municipal_indicator_type_input);
```
```js
const all_title_map_by_indicator = new Map([
["POPULATION_INDICATOR", "Percentatge de la població de 65 anys i més"],
["POPULATION_INDICATOR_VARIATION", `Variació percentual de la població de 65 anys i més entre els anys ${reference_year} i ${latest_year}`],
["RESIDENCE_COVERAGE", "Porcentatge taxa de cobertura de residència per a gent gran"]]);

const all_sub_title_map_by_indicator = new Map([
["POPULATION_INDICATOR", "Nombre de persones de 65 anys i més dividit pel total de la població."],
["POPULATION_INDICATOR_VARIATION", `Diferència entre el percentatge de població de 65 anys i més l’any ${latest_year} i el corresponent a l’any ${reference_year}.`],
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
const nom_comarca_input = Inputs.select(municipal.select('nom_comarca', 'codi_comarca').dedupe('nom_comarca', 'codi_comarca').orderby('nom_comarca'), {label: "Comarca: ", format: x => x.nom_comarca, unique: true})
const nom_comarca = Generators.input(nom_comarca_input);
```
```js
const all_year_serveis_selected = social_services_empty_last_year.params({codi_comarca: nom_comarca.codi_comarca}).filter((d, $) => d.comarca_id == $.codi_comarca).select('year').array('year');
const max_year_serveis = Math.max(...all_year_serveis_selected);
const min_year_serveis = Math.min(...all_year_serveis_selected);
```
```js
const single_comarca_population_input = Inputs.radio(new Map([["Tendència de la població de 65 anys i més", true],
        ["Tendència de l'indicador de població de 65 anys i més", false]]),
    {value: true, label: null});
const single_comarca_population = Generators.input(single_comarca_population_input);
```
```js
const serveis_residence_ratio_input = Inputs.radio(new Map([["Tots els  serveis", true], ["Taxa de cobertura de residència per a gent gran", false]]),
    {value: true, label: null});
const serveis_residence_ratio = Generators.input(serveis_residence_ratio_input)
```
```js
const social_services_comarca = social_services_empty_last_year.params({comarca_id: nom_comarca.codi_comarca}).filter((row, $) => (row.comarca_id === $.comarca_id));
const all_available_services = social_services_comarca.filter(row =>  row.total_capacit > 0).select('service_type_id').dedupe('service_type_id').array('service_type_id');
```
```js
const all_services = Array.from(service_tag_to_complete.entries()).map(k => k[1]);
```
```js
const serveis_input = Inputs.select(new Map(all_available_services.map(s => [service_type._data['service_type_description'][service_type._data['service_type_id'].indexOf(s)], s])), {
    value: [all_available_services[0]],
    label: "Servei"
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
const comarca_name_for_distrit_input = Inputs.select(municipal.select('nom_comarca', 'codi_comarca').dedupe('nom_comarca', 'codi_comarca').orderby('nom_comarca'), {label: "Comarca: ", format: x => x.nom_comarca, unique: true, value: "01"})
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
const municipal_plot = plot_catalunya_map_coverage_municipal(500, single_comarca_map,
ratio_attention_municipal_latest_year, municipal_latest_population, municipal_indicator_type,
color_municipal_map, all_title_map_by_indicator.get(municipal_indicator_type),
municipal_name_label);
```

# Envelliment i Atenció a la Gent Gran a Catalunya (${latest_year})
<div class="story-section">
  <p class="intro">
    [Introduce the story: Why is aging population important? Mention that we'll explore if 
    the growth of the elderly population is being matched by enough care and residence coverage.]
  </p>
</div>

<hr/>

<div class="story-section">
    <h2>On viuen les persones grans a Catalunya?</h2>
    <p>
    Per comprendre la distribució territorial de les persones grans a Catalunya, s’utilitzen dos indicadors que permeten identificar on es concentra la població de 65 anys i més i com ha evolucionat al llarg del temps:
    </p>
    ${catalunya_indicator_or_variation_input}

<div class="grid grid-cols-3">
    <div class="grid-colspan-2">
        <figure class="grafic" style="max-width: none;">
            ${resize((width) => plot_catalunya_map_aged_65(width, comarques_boundaries, catalunya_indicator_or_variation, 
              comarques_latest_population, comarques_reference_population, 
              color_catalunya_map, title_map_by_indicator,
              comarca_name_label, latest_year, reference_year))}
        </figure>
<div class="note">
    <bold>${title_map_by_indicator}</bold>: ${sub_title_map_by_indicator}
</div>
    </div>
    <div class="grid-colspan-1">
        <h2>Catalunya ${latest_year}</h2>
        <div class="grid-colspan-1">
            <div class="card">
                <h4>Població de 65 anys i més</h4>
                <span class="big">${Number(gent_gran_population_latest_year).toLocaleString('ca-ES')}</span>
            </div>  
            <div class="card">
                <h4>Percentatge de la població</h4>
                <span class="big">${Number(latest_indicator_average_catalunya).toLocaleString('ca-ES')}%</span>
            </div>
            <div class="card">
                <h4>Variació respecte a ${reference_year}</h4>
                <span class="big">${sign_difference_reference}${Number(latest_indicator_average_catalunya - reference_year_indicator_average_catalunya).toLocaleString('ca-ES')}%</span>
            </div>
        </div>
    </div>
</div>
</div>

<div class="story-section">
  <h2>Suficiència de places residencials per a la població gran</h2>
  <p>
    Amb l’objectiu d’avaluar l’adequació de l’oferta de places residencials per a persones grans a Catalunya, s’analitza la ràtio de cobertura de llits o places destinades a la població de 65 anys i més.
Segons l’<a href="https://www.acra.cat/estudio-socioecon%C3%B3mico-de-la-atenci%C3%B3n-para-personas-en-situaci%C3%B3n-de-dependencia-en-espa%C3%B1a-informe-final_1123083.pdf">Estudio socioeconómico de la atención para personas en situación de dependencia en España</a>, la ràtio de referència és de 4,11 i 5 places per cada 100 persones majors de 65 anys, valor que orienta la planificació futura dels serveis d’atenció residencial.
Aquesta anàlisi permet identificar els territoris amb una cobertura insuficient i aquells que presenten una oferta més equilibrada respecte a la seva població gran.
  </p>

  <div class="grid grid-cols-3">
    <div class="grid-colspan-2">
        <figure class="grafic" style="max-width: none;">
            ${resize((width) => plot_catalunya_map_coverage(width, comarques_boundaries, 
              ratio_attention_latest_year, "Porcentatge taxa de cobertura de residència per a gent gran",
              comarca_name_label))}
        </figure>
        <div class="note">
        La taxa de cobertura de s'obté a partir del quocient entre el total de població de 65 anys i més i el total oferta de places. S'expressa en tant per cent
        </div>
    </div>
    <div class="grid-colspan-1">
      <div class="card">
          <h4>Places de residència per a gent gran</h4>
          <span class="big">${Number(number_places_residence).toLocaleString('ca-ES')}</span>
      </div>
      <div class="card">
          <h4>Taxa de cobertura</h4>
          <span class="big">${Number(catalunya_ratio_cobertura).toLocaleString('ca-ES')}%</span>
      </div>
      <div class="card">
          <h4>${deficit_superavit} de places (cobertura 4,11%)</h4>
          <span class="big">${Number(deficit_camas_residencia).toLocaleString('ca-ES')}</span>
      </div>
    </div>
  </div>
</div>

<hr/>

<div class="story-section">
  <h2>Evolució de la població gran i dels serveis d’atenció al llarg del temps</h2>
  <p>
    Els indicadors permeten observar com han variat la disponibilitat de places residencials, la distribució dels diferents tipus de serveis i la seva titularitat (pública, privada o social).
Aquesta anàlisi temporal facilita la identificació de tendències i desequilibris territorials en la provisió de serveis destinats a la població gran.
  </p>

  <div class="grid grid-cols-3">
      <h3 class="grid-colspan-2">Tendència de la població i serveis per comarca</h3>
      <div class="grid-colspan-1" style="align-self: center;">
          ${nom_comarca_input}
      </div>
  </div>

  <div class="grid grid-cols-3">
      <div class="grid-colspan-1">
          <h4>Evolució de la població de 65+</h4>
          ${single_comarca_population_input}
          ${resize((width) => plot_legend_trend_population(width, single_comarca_population))}
      </div>
      <div class="grid-colspan-1">
          <h4>Serveis d'assistència</h4>
          ${serveis_residence_ratio_input}
          ${resize((width) => plot_legend_trend_services(width, serveis_residence_ratio, all_available_services, service_type))}
      </div>
      <div class="grid-colspan-1">
          <h4>Qualificació dels serveis</h4>
          ${serveis_input}
          ${resize((width) => plot_legend_trend_iniciative(width, domain_iniciatives, map_inciative_color, service_qualification))} 
      </div>
  </div>

  <div class="grid grid-cols-3">
      <div class="card grid-colspan-1">
          <figure>${resize((width) => plot_trend_population_groups_by_comarca(width, comarca_population, nom_comarca, min_year_serveis, max_year_serveis, single_comarca_population))}</figure>
      </div>
      <div class="card grid-colspan-1">
          <figure>${resize((width) => serveis_residence_ratio ? plot_comarca_by_serveis(width, social_services_empty_last_year, nom_comarca, min_year_serveis, max_year_serveis, all_available_services) : plot_comarca_by_cobertura(width, comarca_coverage, nom_comarca, min_year_serveis, max_year_serveis))}</figure>
      </div>
      <div class="card grid-colspan-1">
          <figure>${resize((width) => plot_services_comarca_by_iniciatives(width, social_services_empty_last_year, nom_comarca, serveis_selected, min_year_serveis, max_year_serveis, all_available_services))}</figure>
      </div>
  </div>

</div>

<hr/>

<div class="story-section">
  <h2>Indicators by district</h2>
  ${comarca_name_for_distrit_input} 
  ${municipal_indicator_type_input}
  <div class="grid grid-cols-3">
    <div class="grid-colspan-2">
        <fig>${municipal_plot}</fig>
        <div class="note">
            <bold>${all_title_map_by_indicator.get(municipal_indicator_type)}</bold>: ${all_sub_title_map_by_indicator.get(municipal_indicator_type)}
        <br/>
            Grey areas indicate no data available.
        </div>
    </div>
    <div class="grid-colspan-1">
        <h2>${comarca_code_for_distrit_value.nom_comarca} ${latest_year}</h2>
        <div class="card">
            <h4>Població de 65 anys i més</h4>
            <span class="big">${Number(comarques_latest_population[comarca_code_for_distrit_value.codi_comarca]?.population_ge65).toLocaleString('ca-ES')}</span>
        </div>  
        <div class="card">
            <h4>Percentatge de la població</h4>
            <span class="big">${Number(comarques_latest_population[comarca_code_for_distrit_value.codi_comarca]?.elderly_indicator).toLocaleString('ca-ES')}%</span>
        </div>
        <div class="card">
          <h4>Places de residència per a gent gran</h4>
          <span class="big">${Number(ratio_attention_latest_year[comarca_code_for_distrit_value.codi_comarca]?.total_capacit).toLocaleString('ca-ES')}</span>
        </div>
        <div class="card">
            <h4>Taxa de cobertura</h4>
            <span class="big">${Number(ratio_attention_latest_year[comarca_code_for_distrit_value.codi_comarca]?.coverage_ratio).toLocaleString('ca-ES')}%</span>
        </div>
        <div class="card">
            <h4>${ratio_attention_latest_year[comarca_code_for_distrit_value.codi_comarca]?.deficit_411 > 0 ? "Dèficit" : "Superàvit"} de places (cobertura 4,11%)</h4>
            <span class="big">${Number(Math.abs(ratio_attention_latest_year[comarca_code_for_distrit_value.codi_comarca]?.deficit_411)).toLocaleString('ca-ES')}</span>
        </div>
    </div>
  </div>
</div>

<style>
.story-section { margin-bottom: 3rem; }
</style>