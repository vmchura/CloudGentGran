```js
const locale_input = Inputs.select(new Map([['Català', 'ca'],
['Castellano', 'es'],
['English', 'en']]), {
  value: "ca",
  label: "Idioma / Language"
});
```
```js
const locale_value = Generators.input(locale_input);
```

```js
const title = {
"ca": "Anàlisi de Dades de Catalunya",
"es": "Análisis de Datos de Cataluña",
"en": "Catalunya Data Analysis"
}[locale_value] || "ERROR";
```

```js
const content = {
  "ca": [`Aquesta plataforma presenta projectes analítics basats en dades obertes de Catalunya, amb el propòsit de proporcionar perspectives clares, fiables i accessibles sobre les dinàmiques socials i territorials de la regió.`,
`El primer estudi, Gent-Gran, examina l'envelliment i l'atenció a la gent gran arreu de Catalunya. El projecte té com a objectiu presentar les dades amb transparència i rigor metodològic, emfatitzant les tendències clau i les disparitats territorials.
Actualment s'estan desenvolupant anàlisis addicionals sobre altres temes, seguint el mateix enfocament — i cada cop més rigorós.`,
`Els comentaris, recomanacions i retroalimentació constructiva són benvinguts. Podeu contactar-me directament a través de LinkedIn per compartir les vostres perspectives o suggeriments per a futurs estudis.
Tot el codi font és obert i està disponible en un únic repositori de GitHub.`],
  "es": [`This platform presents analytical projects based on open data from Catalonia, with the purpose of providing clear, reliable, and accessible insights into the region's social and territorial dynamics.`,
`The first study, Gent-Gran, examines aging and elderly care across Catalonia. The project aims to present data with transparency and methodological rigor, emphasizing key trends and territorial disparities.
Additional analyses on other topics are currently in development, following the same — and increasingly rigorous — approach.`,
`Comments, recommendations, and constructive feedback are welcome. You may contact me directly via LinkedIn to share your insights or suggestions for future studies.
All source code is open and available in a single GitHub repository`],
  "en": [`Esta plataforma presenta proyectos analíticos basados en datos abiertos de Cataluña, con el propósito de proporcionar perspectivas claras, fiables y accesibles sobre las dinámicas sociales y territoriales de la región.`,
`El primer estudio, Gent-Gran, examina el envejecimiento y la atención a las personas mayores en toda Cataluña. El proyecto tiene como objetivo presentar los datos con transparencia y rigor metodológico, enfatizando las tendencias clave y las disparidades territoriales.
Actualmente se están desarrollando análisis adicionales sobre otros temas, siguiendo el mismo enfoque — cada vez más riguroso.`,
`Se agradecen comentarios, recomendaciones y retroalimentación constructiva. Puede contactarme directamente a través de LinkedIn para compartir sus perspectivas o sugerencias para futuros estudios.
Todo el código fuente es abierto y está disponible en un único repositorio de GitHub.`]}[locale_value] || "ERROR";
```

<div>${locale_input}</div>
<h1>${title}</h1>
<p>${content[0]}</p>
<p>${content[1]}</p>
<p>${content[2]}</p>

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

