export class SocialServicesDataService {
  constructor(db) {
    this.db = db;
    this.cache = new Map();
  }

  async getServiceTypeLabels() {
    if (this.cache.has('service_types')) return this.cache.get('service_types');
    
    const result = await this.db.query(`
      SELECT service_type_id, service_type_description 
      FROM social_services.service_type
    `);
    
    const map = new Map(result.toArray().map(d => [d.service_type_id, d.service_type_description]));
    this.cache.set('service_types', map);
    return map;
  }

  async getServiceQualificationLabels() {
    if (this.cache.has('service_qualifications')) return this.cache.get('service_qualifications');
    
    const result = await this.db.query(`
      SELECT service_qualification_id, service_qualification_description 
      FROM social_services.service_qualification
    `);
    
    const map = new Map(result.toArray().map(d => [d.service_qualification_id, d.service_qualification_description]));
    this.cache.set('service_qualifications', map);
    return map;
  }

  async getComarcaServices(comarcaId, minYear) {
    const cacheKey = `comarca_services_${comarcaId}_${minYear}`;
    if (this.cache.has(cacheKey)) return this.cache.get(cacheKey);

    const result = await this.db.query(`
      SELECT DISTINCT service_type_id
      FROM social_services.social_services_empty_last_year
      WHERE comarca_id = ${comarcaId}
        AND total_capacit > 0
    `);

    const services = result.toArray().map(d => d.service_type_id);
    this.cache.set(cacheKey, services);
    return services;
  }

  async getComarcaServiceRows(comarcaId) {
    const cacheKey = `comarca_service_rows_${comarcaId}`;
    if (this.cache.has(cacheKey)) return this.cache.get(cacheKey);

    const result = await this.db.query(`
      SELECT DISTINCT
        st.service_type_id,
        st.service_type_description
      FROM social_services.social_services_empty_last_year s
      JOIN social_services.service_type st USING (service_type_id)
      WHERE s.comarca_id = ${comarcaId}
        AND s.total_capacit > 0
      ORDER BY st.service_type_description
    `);

    this.cache.set(cacheKey, result.toArray());
    return result.toArray();
  }

  async getComarcaTimeRange(comarcaId) {
    const cacheKey = `comarca_time_range_${comarcaId}`;
    if (this.cache.has(cacheKey)) return this.cache.get(cacheKey);

    const result = await this.db.queryRow(`
      SELECT
        MAX(year) AS max_year_serveis,
        MIN(year) AS min_year_serveis
      FROM social_services.social_services_empty_last_year
      WHERE comarca_id = ${comarcaId}
    `);

    this.cache.set(cacheKey, result);
    return result;
  }

  async getComarcas() {
    if (this.cache.has('comarques')) return this.cache.get('comarques');

    const result = await this.db.query(`
      SELECT DISTINCT comarca_name, comarca_id
      FROM social_services.municipal
      ORDER BY comarca_name
    `);

    this.cache.set('comarques', result.toArray());
    return result.toArray();
  }
}
