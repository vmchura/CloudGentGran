import * as aq from "npm:arquero";

export async function loadData(social_services_zip_data) {
  const comarca_population = aq.fromJSON(await social_services_zip_data.file("comarca_population.json").json());
  const social_services_empty_last_year = aq.fromJSON(await social_services_zip_data.file("social_services_empty_last_year.json").json());
  const municipal_coverage = aq.fromJSON(await social_services_zip_data.file("municipal_coverage.json").json());
  const comarca_coverage = aq.fromJSON(await social_services_zip_data.file("comarca_coverage.json").json());
  const municipal = aq.fromJSON(await social_services_zip_data.file("municipal.json").json());
  const service_type = aq.fromJSON(await social_services_zip_data.file("service_type.json").json());
  const service_qualification = aq.fromJSON(await social_services_zip_data.file("service_qualification.json").json());

  return {
    comarca_population,
    social_services_empty_last_year,
    municipal_coverage,
    comarca_coverage,
    municipal,
    service_type,
    service_qualification
  };
}