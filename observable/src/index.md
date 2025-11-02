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
  "ca": `Aquesta plataforma presenta projectes analítics basats en dades obertes de Catalunya, amb el propòsit de proporcionar perspectives clares, fiables i accessibles sobre les dinàmiques socials i territorials de la regió.
El primer estudi, Gent-Gran, examina l'envelliment i l'atenció a la gent gran arreu de Catalunya. El projecte té com a objectiu presentar les dades amb transparència i rigor metodològic, emfatitzant les tendències clau i les disparitats territorials.
Actualment s'estan desenvolupant anàlisis addicionals sobre altres temes, seguint el mateix enfocament — i cada cop més rigorós.
Els comentaris, recomanacions i retroalimentació constructiva són benvinguts. Podeu contactar-me directament a través de LinkedIn per compartir les vostres perspectives o suggeriments per a futurs estudis.
Tot el codi font és obert i està disponible en un únic repositori de GitHub.`,
  "es": `This platform presents analytical projects based on open data from Catalonia, with the purpose of providing clear, reliable, and accessible insights into the region's social and territorial dynamics.
The first study, Gent-Gran, examines aging and elderly care across Catalonia. The project aims to present data with transparency and methodological rigor, emphasizing key trends and territorial disparities.
Additional analyses on other topics are currently in development, following the same — and increasingly rigorous — approach.
Comments, recommendations, and constructive feedback are welcome. You may contact me directly via LinkedIn to share your insights or suggestions for future studies.
All source code is open and available in a single GitHub repository`,
  "en": `Esta plataforma presenta proyectos analíticos basados en datos abiertos de Cataluña, con el propósito de proporcionar perspectivas claras, fiables y accesibles sobre las dinámicas sociales y territoriales de la región.
El primer estudio, Gent-Gran, examina el envejecimiento y la atención a las personas mayores en toda Cataluña. El proyecto tiene como objetivo presentar los datos con transparencia y rigor metodológico, enfatizando las tendencias clave y las disparidades territoriales.
Actualmente se están desarrollando análisis adicionales sobre otros temas, siguiendo el mismo enfoque — cada vez más riguroso.
Se agradecen comentarios, recomendaciones y retroalimentación constructiva. Puede contactarme directamente a través de LinkedIn para compartir sus perspectivas o sugerencias para futuros estudios.
Todo el código fuente es abierto y está disponible en un único repositorio de GitHub.`}[locale_value] || "ERROR";
```

<div>${locale_input}</div>
<h1>${title}</h1>
<p>${content}</p>
