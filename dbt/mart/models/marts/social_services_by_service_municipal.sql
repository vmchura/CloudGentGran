{{ adapter_aware_table_config () }}
WITH social_services AS (
    SELECT
        social_service_register_id,
        service_qualification_id,
        service_type_id,
        comarca_id,
        municipal_id,
        EXTRACT(YEAR FROM inscription_date) AS year,
        EXTRACT(MONTH FROM inscription_date) AS month,
        capacity
    FROM
        {{ read_staging_data ('social_services', 'downloaded_date', var ('downloaded_date')) }}
    WHERE
        downloaded_date = '{{ var("downloaded_date") }}'
        AND capacity > 0
        AND service_type_id IN ('DAY-001', 'RES-003', 'RES-002', 'TUT-001', 'RES-001')
),
social_services_with_input_qualification AS (
    SELECT
        (
            CASE WHEN service_qualification_id IS NULL THEN
                CASE social_service_register_id
                WHEN 'S07873' THEN
                    -- S07873 Residència assistida Can Serra: És un servei d'ASPROSEAT: Asproseat grup és un conjunt d’entitats socials d’àmbit català que té com a finalitat principal
                    'PRV-002'
                WHEN 'S07874' THEN
                    -- S07874 Centre de dia Can Serra: És un servei d'ASPROSEAT, Asproseat grup és un conjunt d’entitats socials d’àmbit català que té com a finalitat principal
                    'PRV-002'
                WHEN 'S10642' THEN
                    -- S10642 Residència de gent gran El Tossalet: El Tossalet és una Residència i Centre de dia per a persones grans, situada a Lleida, a Cervià de les Garrigues (Lleida) gestionat per la Fundació Persona i Valors des del 2021. És un centre especialitzat en persones grans amb necessitats específiques.
                    'PRV-002'
                WHEN 'S10643' THEN
                    -- S10643 Centre de dia El Tossalet: El Tossalet és una Residència i Centre de dia per a persones grans, situada a Lleida, a Cervià de les Garrigues (Lleida) gestionat per la Fundació Persona i Valors des del 2021. És un centre especialitzat en persones grans amb necessitats específiques.
                    'PRV-002'
                WHEN 'S10486' THEN
                    -- S10486 Residència Seniors Ceritània: Clariane es la primera red europea de residencias para las personas de la tercera edad con clínicas especializadas, centros asistenciales con distintas modalidades y hospitalización a domicilio. Como empresa comprometida con el servicio asistencial
                    'PRV-001'
                WHEN 'S07316' THEN
                    -- S07316 Residencia Idea Vilapicina: Juntos definieron un propósito corporativo diferenciador: mejorar la calidad de vida de las personas con un enfoque ético de los cuidados.
                    'PRV-001'
                END
            ELSE
                service_qualification_id
            END) AS service_qualification_id,
        service_type_id,
        comarca_id,
        municipal_id,
        year,
        month,
        capacity
    FROM
        social_services
)
SELECT
    service_qualification_id,
    service_type_id,
    comarca_id,
    municipal_id,
    year,
    month,
    SUM(capacity) as total_capacit
FROM
    social_services_with_input_qualification
GROUP BY
    service_qualification_id,
    service_type_id,
    comarca_id,
    municipal_id,
    year,
    month
