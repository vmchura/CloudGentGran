```js
const social_services_zip_data = FileAttachment("./data/social_services.zip").zip();
const comarques_boundaries = FileAttachment("./data/comarques-1000000.json").json();
const municipals_boundaries = FileAttachment("./data/municipis-1000000.json").json();
  
import {loadData} from "./components/data-loader.js";
import {calculateIndicators} from "./components/indicators.js";
import {
    getColorCatalunyaMap,
    plot_catalunya_map_aged_65,
    plot_catalunya_map_coverage
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
  service_qualification
} = data;
```
```js
const indicators = calculateIndicators(comarca_population, social_services_empty_last_year, comarca_coverage);
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
  comarques_reference_population
} = indicators;
```
```js
const nom_comarques = municipal.select('nom_comarca').dedupe('nom_comarca').array('nom_comarca');
```
```js
const catalunya_indicator_or_variation_input = Inputs.radio(new Map([
    ["Percentatge de la població de 65 anys i més", 1],
    [`Variació percentual entre els anys ${reference_year} i ${latest_year}`, 2]]),
    {value: 1});
const catalunya_indicator_or_variation = Generators.input(catalunya_indicator_or_variation_input);
```
```js
const all_title_map_by_indicator = ["Percentatge de la població de 65 anys i més",
    `Variació percentual de la població de 65 anys i més entre els anys ${reference_year} i ${latest_year}`];
const title_map_by_indicator = all_title_map_by_indicator[catalunya_indicator_or_variation - 1];
const all_sub_title_map_by_indicator = ["Nombre de persones de 65 anys i més dividit pel total de la població.",
    `Diferència entre el percentatge de població de 65 anys i més l’any ${latest_year} i el corresponent a l’any ${reference_year}.`];
const sub_title_map_by_indicator = all_sub_title_map_by_indicator[catalunya_indicator_or_variation - 1];
```
```js
const color_catalunya_map = getColorCatalunyaMap(catalunya_indicator_or_variation, latest_indicator_average_catalunya_integer, range_colours_indicator);
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


# Envelliment i Atenció a la Gent Gran a Catalunya (2024)
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
              color_catalunya_map, title_map_by_indicator))}
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
              ratio_attention_latest_year, "Porcentatge taxa de cobertura de residència per a gent gran"))}
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
  <h2>4️⃣ Què ens diu tot això?</h2>
  <p class="conclusion">
    [Wrap up the story. Discuss whether Catalonia is aging faster than it expands care capacity,
    mention regional inequalities, and suggest potential implications for policymakers.]
  </p>
</div>

<style>
.story-section { margin-bottom: 3rem; }
</style>