# Bitácora — Migración LocalStack → MiniStack

## 2026-08-05 · Entrada 1: Contexto y motivación

LocalStack movió sus servicios core detrás de un plan de pago, por lo que deja
de ser viable como emulador AWS gratuito para desarrollo local y CI de este
proyecto. Se migra a [MiniStack](https://github.com/ministackorg/ministack):

- 60+ servicios AWS en un solo puerto (4566), drop-in compatible con boto3 / AWS CLI / CDK.
- Imagen ~270 MB (~110 MB la estándar) y ~30 MB RAM en idle vs ~1 GB / ~500 MB de LocalStack.
- Arranque < 2 s. Licencia MIT.
- Mantiene compatibilidad con el endpoint de health de LocalStack (`/_localstack/health`).
- Imagen `:full` incluye DuckDB → Athena ejecuta SQL real (este proyecto usa
  Athena vía `dbt_athena_operator.py` y `ATHENA_DATABASE_NAME`, por lo que se
  usa la imagen `ministackorg/ministack:full`).

Alcance de esta entrada: `docker-compose.local.yaml`. Cambios en DAGs, scripts
y operators quedan registrados como trabajo pendiente (sección final).

---

## Entrada 2: Cambios propuestos en `docker-compose.local.yaml`

### 2.1 Servicio `localstack` → `ministack`

**Antes:**
```yaml
localstack:
  container_name: cloudgentgran-localstack
  image: localstack/localstack:latest
```

**Después:**
```yaml
ministack:
  container_name: cloudgentgran-ministack
  image: ministackorg/ministack:full
```

**Por qué:** nueva imagen. Se usa el tag `:full` (Debian/glibc con DuckDB,
psycopg2, pymysql) porque el pipeline ejecuta SQL real contra Athena en local
(dbt + `DbtAthenaOperator`). Con la imagen estándar Athena devolvería resultados
mock y los modelos dbt no podrían validarse.

### 2.2 Variables de entorno del emulador

**Antes:**
```yaml
- DEBUG=1
- SERVICES=s3,lambda,cloudformation,iam,logs,sts,events,ssm
- DOCKER_HOST=unix:///var/run/docker.sock
- LAMBDA_DOCKER_NETWORK=cloudgentgran-local
- LAMBDA_RUNTIME_EXECUTOR_TIMEOUT=900
- AWS_DEFAULT_REGION=eu-west-1
- AWS_ACCESS_KEY_ID=test
- AWS_SECRET_ACCESS_KEY=test
```

**Después:**
```yaml
- LOG_LEVEL=DEBUG
- MINISTACK_REGION=eu-west-1
- LAMBDA_EXECUTOR=docker
- DOCKER_NETWORK=cloudgentgran-local
- PERSIST_STATE=1
- STATE_DIR=/var/lib/ministack
```

**Por qué, línea a línea:**

- `DEBUG=1` → `LOG_LEVEL=DEBUG`: MiniStack usa `LOG_LEVEL` (`DEBUG|INFO|WARNING|ERROR`).
- `SERVICES=...` se elimina: MiniStack no carga servicios selectivamente; los
  60+ servicios están siempre activos en el gateway. No hay equivalente.
- `DOCKER_HOST` se elimina: MiniStack detecta el socket montado en
  `/var/run/docker.sock` automáticamente (Docker-in-Docker); no requiere variable.
- `LAMBDA_DOCKER_NETWORK` → `DOCKER_NETWORK`: en MiniStack `LAMBDA_DOCKER_NETWORK`
  existe solo como alias legacy (Lambda únicamente). `DOCKER_NETWORK` cubre todos
  los servicios con contenedores anidados (Lambda, RDS, ElastiCache). Mismo valor:
  la red compose `cloudgentgran-local` para que las Lambda alcancen el gateway en
  `http://ministack:4566`.
- `LAMBDA_EXECUTOR=docker` (nueva): MiniStack ejecuta Lambda en subproceso local
  por defecto. Se fuerza `docker` para paridad con el comportamiento anterior de
  LocalStack y aislamiento real. Nota: los runtimes `provided.al2023` (Lambdas
  Rust del proyecto) usan Docker siempre, independientemente de esta variable.
- `LAMBDA_RUNTIME_EXECUTOR_TIMEOUT=900` se elimina: no existe equivalente en
  MiniStack. La gestión de contenedores Lambda se controla con
  `LAMBDA_WARM_TTL_SECONDS` (default 300 s), que no hace falta tocar.
- `AWS_DEFAULT_REGION` → `MINISTACK_REGION`: la región que reporta el emulador
  en ARNs y respuestas se configura con `MINISTACK_REGION`. Se mantiene `eu-west-1`.
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` se eliminan: el emulador no
  valida credenciales; eran cosméticas en LocalStack.
- `PERSIST_STATE=1` + `STATE_DIR` (nuevas): el setup anterior persistía estado en
  `./localstack/volume`. MiniStack persiste todo el estado de servicios con
  `PERSIST_STATE=1` en `STATE_DIR`, montado como volumen nombrado
  `ministack-state` para no mezclar con el directorio legacy `./localstack/`.

### 2.3 Healthcheck

**Antes:**
```yaml
test: ["CMD", "curl", "-f", "http://localhost:4566/_localstack/health"]
interval: 60s
start_period: 60s
```

**Después:**
```yaml
test: ["CMD-SHELL", "python3 -c \"import urllib.request;urllib.request.urlopen('http://localhost:4566/_ministack/health')\""]
interval: 10s
start_period: 10s
```

**Por qué:**
- Endpoint nativo `/_ministack/health` (MiniStack también responde en
  `/_localstack/health` por compatibilidad, pero se usa el nativo).
- La imagen MiniStack es mínima (~110 MB) y no garantiza `curl`; sí garantiza
  `python3` (es una imagen Python). Se usa `urllib` para el check.
- `interval`/`start_period` bajan de 60 s a 10 s: MiniStack arranca en < 2 s;
  los valores de LocalStack estaban pensados para su arranque lento. Airflow
  deja de esperar un minuto innecesario en cada `up`.

### 2.4 Recursos del contenedor

**Antes:**
```yaml
shm_size: '1G'
deploy:
  resources:
    limits: { memory: 2G, cpus: '1.5' }
    reservations: { memory: 1G, cpus: '0.5' }
```

**Después:**
```yaml
deploy:
  resources:
    limits: { memory: 1G, cpus: '1.0' }
    reservations: { memory: 256M, cpus: '0.25' }
```

**Por qué:** MiniStack consume ~30 MB RAM en idle (vs ~500 MB de LocalStack).
`shm_size: 1G` existía para el rendimiento de Lambda en LocalStack; con
`LAMBDA_EXECUTOR=docker` las Lambdas corren en contenedores hermanos con su
propia shm, por lo que se elimina. Los límites se reducen acorde.

### 2.5 Volumen de estado (nuevo)

```yaml
volumes:
  - "/var/run/docker.sock:/var/run/docker.sock"
  - "ministack-state:/var/lib/ministack"
```

**Por qué:** el socket se mantiene (necesario para Lambda/RDS en Docker). Se
añade el volumen nombrado `ministack-state` para `PERSIST_STATE=1`. No se reutiliza
`./localstack/volume`: el formato de estado es incompatible y se quiere poder
volver atrás durante la migración.

### 2.6 Red y `depends_on`

**Por qué:** el anchor `airflow-common-depends-on` cambia `localstack:` por
`ministack:` (misma condición `service_healthy`). El servicio sigue en la red
`cloudgentgran-local` para que Airflow y las Lambda lo resuelvan por nombre.

### 2.7 Variables de Airflow (`x-airflow-common`)

**Antes:**
```yaml
# LocalStack Integration
AWS_ENDPOINT_URL: http://localstack:4566
...
AIRFLOW_CONN_LOCALSTACK_DEFAULT: 'aws://test:test@localstack:4566/?region_name=eu-west-1&endpoint_url=http%3A%2F%2Flocalstack%3A4566'
```

**Después:**
```yaml
# MiniStack Integration (AWS emulator)
AWS_ENDPOINT_URL: http://ministack:4566
...
AIRFLOW_CONN_LOCALSTACK_DEFAULT: 'aws://test:test@ministack:4566/?region_name=eu-west-1&endpoint_url=http%3A%2F%2Fministack%3A4566'
```

**Por qué:** `AWS_ENDPOINT_URL` es estándar de los SDKs de AWS y apunta al
nuevo hostname. **Se conserva el conn-id `localstack_default`** a propósito:
5 DAGs lo referencian (`catalunya_social_services_dag.py`, `catalunya_catalog_initializer.py`,
`catalunya_comarques_boundaries_dag.py`, `catalunya_long_term_update.py`,
`standalone_observable.py`). Mantener el id hace la migración drop-in; el
renombrado a `ministack_default` queda como limpieza posterior.

### 2.8 `airflow-init`

- `pip install awscli-local` se elimina: `awscli-local`/`awslocal` es un wrapper
  específico de LocalStack. Con MiniStack basta la AWS CLI estándar con
  `--endpoint-url` (o la variable `AWS_ENDPOINT_URL`, ya presente).
- `airflow variables set localstack_endpoint "http://localstack:4566"` →
  `... "http://ministack:4566"`. Se conserva el nombre de variable
  `localstack_endpoint` (ningún DAG lo usa actualmente; renombrado pendiente).
- La conexión `localstack_default` del init cambia solo el `endpoint_url` a
  `http://ministack:4566` (misma razón que 2.7).
- Mensajes de log actualizados (LocalStack → MiniStack).

---

## 2026-08-06 · Entrada 3: `restart: always` eliminado del compose

**Cambio:** se eliminaron las 4 directivas `restart` (`postgres`, `ministack`,
`airflow`, `airflow-init`) de `docker-compose.local.yaml`.

**Por qué:** el default de Docker es `no`. Con `restart: always` el daemon
levantaba todo el stack en cada boot sin intervención del usuario. Ahora el
entorno solo arranca con `docker compose ... up -d` manual. Efecto secundario:
si un contenedor crashea, queda detenido (visible con `docker compose ps`).

---

## Entrada 4: Revisión profunda de `scripts/start-local-dev.sh`

Revisión estática (sin ejecutar). Hallazgos y cambios:

### 4.1 `LOCALSTACK_VOLUME_DIR=./localstack/volume` → eliminada (bug real)

**Problema:** el compose ya no monta `./localstack/volume` (bind mount de
LocalStack); MiniStack persiste en el volumen nombrado
`cloudgentgran-ministack-state` (ver Entrada 2.5). El script hacía
`rm -rf ./localstack/volume` en `full-deploy` y `destroy`: **borraba un
directorio huérfano y dejaba intacto el estado real de MiniStack** — el
"clean start" no era limpio.

**Cambio:** variable sustituida por `MINISTACK_STATE_VOLUME` y:

- `full-deploy`: `docker volume rm -f cloudgentgran-ministack-state` tras el
  `down` (antes de recrear con `up`).
- `destroy`: `down -v` ya elimina el volumen nombrado; se quita el `rm -rf`.
- Alternativa documentada en el usage: reset en caliente sin reiniciar con
  `curl -X POST http://localhost:4566/_ministack/reset`.

### 4.2 Health checks: grep de JSON → HTTP 200

**Problema:** se hacía grep de `"available"` / `"running"` sobre
`/_localstack/health` — formato de estado propio de LocalStack. MiniStack
expone `/_ministack/health` con formato distinto (y el alias `/_localstack/health`
solo por compatibilidad). Depender del JSON es frágil.

**Cambio:** `curl -sf http://localhost:4566/_ministack/health` (éxito = HTTP
200). Timeouts 180s → 60s: MiniStack arranca en < 2 s, el margen sobra.

### 4.3 `sleep 90` y `sleep 30` eliminados

**Por qué:** eran para la inicialización lenta de LocalStack. MiniStack está
listo al responder 200 en health. Se deja `sleep 5` de cortesía antes del
deploy CDK (servicios con contenedores anidados).

### 4.4 `docker exec cloudgentgran-localstack awslocal ...` → aws CLI bundled

**Problema:** el contenedor se renombró a `cloudgentgran-ministack` y
`awslocal` (wrapper de `awscli-local`, específico de LocalStack) no existe en
la imagen MiniStack.

**Cambio:** la imagen MiniStack incluye AWS CLI estándar →
`docker exec cloudgentgran-ministack aws --endpoint-url=http://localhost:4566 ...`
en `validate_deployment` (Lambda count y S3 buckets). Nombre del contenedor
también corregido en `show_logs`.

### 4.5 `docker-compose` (v1) → `docker compose` (v2)

**Por qué:** v1 está EOL; el script mezclaba ambas. Unificado a v2 y al uso de
`"$COMPOSE_FILE"` en todos los comandos.

### 4.6 Airflow health `/health` → `/api/v2/monitor/health`

**Por qué:** Airflow 3 eliminó `/health`; el healthcheck del compose ya usaba
`/api/v2/monitor/health`. El script esperaba un endpoint inexistente → falso
timeout de 300 s en `monitor_startup`.

### 4.7 Mensajes y textos

Referencias LocalStack → MiniStack en usage, logs y URLs
(`/_ministack/health`). Se mantiene `localstack_default` como conn-id en el
test de conexión (compatibilidad DAGs, ver Entrada 2.7).

### Fuera de alcance de esta entrada

`infrastructure/deploy-localstack.sh` sigue orientado a LocalStack: usa
`cdklocal` (wrapper de `aws-cdk-local` con endpoints hardcodeados a LocalStack)
y health `/_localstack/health`. Requiere verificar si `cdklocal` funciona contra
MiniStack (compatible con el endpoint de CloudFormation) o migrar a `cdk deploy`
con `--endpoint-url` / variables de entorno. **Pendiente para la próxima entrada.**

---

## Entrada 5: Build de Rust Lambdas — `docs/rust_lambda_builds.md` y `scripts/test-act.sh`

### 5.1 `docs/rust_lambda_builds.md`

**Hallazgo:** todos los comandos `cargo lambda deploy/invoke` usaban
`-p localstack` y los `aws` CLI `--profile localstack`.

**Por qué:** `-p` / `--profile` es solo el nombre de un perfil en
`~/.aws/credentials` + `~/.aws/config`; no hay nada LocalStack-específico en el
mecanismo, pero el nombre quedó obsoleto y el perfil hay que crearlo igual.

**Cambio:** renombrado a perfil `ministack` y añadida sección de setup del
perfil (credentials `test`/`test`, region `eu-west-1`). Alternativa documentada:
env vars + `--endpoint-url` sin perfil. Añadido pointer a
`./scripts/test-act.sh --local-build` para build de todas las lambdas de una vez.

**Nota de compatibilidad:** `cargo lambda deploy` usa `CreateFunction` con
`ZipFile` — soportado por MiniStack. Las lambdas Rust usan runtime
`provided.al2023`, que MiniStack ejecuta **siempre** en contenedor Docker (RIE),
independientemente de `LAMBDA_EXECUTOR`. Requiere el socket de Docker montado
(ya está en el compose).

### 5.2 `scripts/test-act.sh`

**Cambios (cosméticos + endpoint):**

- `check_localstack` → `check_ministack`: health `/_ministack/health` con
  `curl -sf` (HTTP 200), mensaje de arranque corregido:
  `docker compose -f docker-compose.local.yaml up -d ministack`
  (antes apuntaba a `cd localstack && docker-compose up -d`, ruta inexistente).
- `LOCALSTACK_ENDPOINT` → `MINISTACK_ENDPOINT` (mismo valor `http://localhost:4566`).
- Textos de ayuda, banner, `.secrets` e instrucciones de deploy actualizados.
- Sin cambios funcionales: `--local-build` (cargo lambda build + zip) no toca
  el emulador; `.secrets` ya usaba `AWS_ENDPOINT_URL` estándar.

**Pendiente:** las instrucciones de deploy del script mencionan `cdklocal`
(misma duda que `deploy-localstack.sh`, Entrada 4).

---

## 2026-08-06 · Entrada 6: Gate `createAirflowUser` — MiniStack CFN no soporta `AWS::IAM::User`

### Síntoma

`cdklocal deploy` fallaba con rollback:

```
CREATE_FAILED | AWS::IAM::User | IamInfrastructure/AirflowUser
Unsupported resource type: AWS::IAM::User
```

### Root cause (revisión estática)

El CDK no cambió desde el último deploy real a AWS. Diferencia de emuladores:

- **AWS real**: soporta todos los resource types.
- **LocalStack**: su CloudFormation mock-acepta casi cualquier type aunque no
  lo implemente.
- **MiniStack**: strict — solo los types de su lista oficial
  (`AWS::IAM::Role`, `AWS::IAM::Policy`, `AWS::IAM::InstanceProfile`,
  `AWS::IAM::ManagedPolicy`). `AWS::IAM::User` y `AWS::IAM::AccessKey`
  **no están soportados**.

`AirflowUser` (`iam-construct.ts`, `dokku-airflow-assumer-{env}` + AccessKey)
existe para producción: Airflow en Dokku hace `sts:AssumeRole` al cross-account
role. En local no se ejerce: el Airflow del compose usa creds estáticas
`test/test` contra MiniStack.

### Fix

Gate por CDK context flag `createAirflowUser` (default `true` — AWS real sin
cambios):

1. **`infrastructure/lib/iam-construct.ts`**
   - `IamConstructProps.createAirflowUser?: boolean`.
   - `airflowUser`/`airflowAccessKey` pasan a opcionales; bloque de creación
     envuelto en `if (props.createAirflowUser ?? true)`.
   - `airflowCrossAccountRole.assumedBy` usa `ArnPrincipal(user.userArn)` si
     existe, `AccountRootPrincipal` si no (principal válido para sintetizar;
     el assume-role no se valida en el emulador).
2. **`infrastructure/lib/infrastructure-stack.ts`**
   - Pasa el flag desde context: `![false, 'false'].includes(tryGetContext(...))`.
     **Gotcha**: los valores `-c` por CLI llegan como string — comparar solo con
     `!== false` no funciona (verificado: el synth seguía emitiendo el User).
   - Los 3 `CfnOutput` del user/accesskey condicionados a su existencia.
3. **`infrastructure/deploy-localstack.sh`**
   - `cdklocal deploy ... -c createAirflowUser=false`.

### Verificación

- `npm run build` ✅ (TS strict sin errores).
- `npx cdk synth -c createAirflowUser=false` → 0 recursos `AWS::IAM::User`/`AccessKey`.
- `npx cdk synth` (default) → 2 (comportamiento AWS sin cambios).
- `npm test` → 4/4 pass.

---

## Entrada 7: Stack colgado en `Custom::S3AutoDeleteObjects` — `MINISTACK_HOST`

### Síntoma

`cdklocal deploy` avanzaba hasta 24/49 y se quedaba en
`CREATE_IN_PROGRESS` indefinido en el custom resource
`S3AutoDeleteObjects` (Lambda provider nodejs que vacía buckets en destroy).

### Diagnóstico (logs MiniStack)

- Imagen `public.ecr.aws/lambda/nodejs:22` pulleada (~412 MB, primera vez)
  y contenedor Lambda arrancado OK (20:44:13, "cold-start container added
  to pool").
- **Cero requests PUT al gateway** en todo el log: la Lambda nunca devolvió
  la respuesta cfn-response a CloudFormation.
- Contenedor recolectado por TTL a los 5 min; CFN siguió esperando forever.

### Root cause

MiniStack genera las response URLs de CFN custom resources con
`MINISTACK_HOST` (default `localhost`). Con `LAMBDA_EXECUTOR=docker` la Lambda
corre en un contenedor hermano dentro de la red `cloudgentgran-local` →
`localhost:4566` dentro del contenedor es él mismo → el POST de cfn-response
nunca alcanza MiniStack.

### Fix definitivo (tras 2 iteraciones fallidas)

**Root cause real** (código MiniStack, `lambda_runtime.py:664` y
`lambda_svc.py:_invoke_rie`):

> *"cfn-response.js calls https.request unconditionally for the ResponseURL
> PUT, and also drops the port when constructing options."*

El provider framework de CDK **fuerza HTTPS y descarta el puerto** al hacer el
PUT a la ResponseURL → la conexión va al puerto 443 → `ECONNREFUSED`. El shim
que lo corrige (`patchAwsSdk`, downgrade https→http + puerto correcto) solo se
inyecta en el **warm worker pool** (executor local de python/nodejs), **no en
el RIE de Docker**. Conclusión: `LAMBDA_EXECUTOR=docker` es incompatible con
custom resources de CDK.

Iteraciones fallidas documentadas:
1. `MINISTACK_HOST=ministack` → la URL era correcta pero el PUT iba a
   `https://ministack:443` (puerto descartado por cfn-response) → ECONNREFUSED.
2. `MINISTACK_HOST=ministack:4566` → URL `http://ministack:4566:4566/...`
   inválida (`_response_url()` concatena `_HOST:_PORT`).

**Cambio final en compose:**
- Eliminado `LAMBDA_EXECUTOR=docker` → default (warm worker pool) para
  python/nodejs. Los custom resources CDK funcionan porque el shim https→http
  sí aplica.
- Eliminado `MINISTACK_HOST` → default `localhost`: el warm pool corre dentro
  del propio contenedor ministack, así que `http://localhost:4566` resuelve
  bien. Las lambdas en Docker RIE (runtime `provided.*`, p.ej. las Rust del
  proyecto) reciben `AWS_ENDPOINT_URL=http://host.docker.internal:4566` con
  `extra_hosts` automático, y MiniStack reescribe las ResponseURL
  localhost→host.docker.internal (`_invoke_rie`, issue #1149).
- Se mantiene `DOCKER_NETWORK=cloudgentgran-local` (necesario para las RIE).

**Lección:** `LAMBDA_EXECUTOR=docker` solo es deseable si NO se usan custom
resources CDK/CFN con providers nodejs.

**Postdata:** el warm pool tampoco resolvió este recurso concreto — el handler
requiere `@aws-sdk/client-s3` y MiniStack no tiene stub (S3 es REST-XML). El
deploy se desbloqueó finalmente con el gate de Entrada 8.

**Trade-off:** las URLs embebidas en respuestas (SQS QueueUrl, SNS
subscriptions, API Gateway endpoints, Lambda layers) llevarán host `ministack`
— solo afecta a clientes desde el host que consuman esas URLs. Los clientes
con `--endpoint-url=http://localhost:4566` explícito (scripts, aws cli) no se
ven afectados.

### Recuperación del deploy colgado

```bash
# reset de estado sin reiniciar (wipea el stack zombie)
curl -X POST http://localhost:4566/_ministack/reset
# o limpio completo:
./scripts/start-local-dev.sh full-deploy
```

### Notas

- La imagen nodejs RIE (~412 MB) ya queda cacheada en Docker; próximos cold
  starts son rápidos.
- MiniStack no parchea las response URLs de custom resources al estilo
  LocalStack — este patrón (CFN provider → Lambda en Docker → PUT de vuelta)
  es el caso más sensible a `MINISTACK_HOST`.

---

## 2026-08-07 · Entrada 8: Gate `autoDeleteObjects` — warm pool sin `@aws-sdk/client-s3`

### Síntoma

Tras la Entrada 7, el deploy seguía colgado en `Custom::S3AutoDeleteObjects`,
pero el error cambió (logs ministack):

```
ERROR [lambda] Warm worker execution error ...: Worker init failed:
Cannot find module '@aws-sdk/client-s3'
```

### Root cause

Catch-22 de los custom resources CDK en MiniStack:

- **Docker RIE** (Entrada 7): cfn-response fuerza HTTPS + descarta puerto →
  ECONNREFUSED 443. Sin shim disponible.
- **Warm worker pool** (default): el require-intercept de MiniStack tiene stubs
  para clients JSON-RPC (`@aws-sdk/client-ssm`, `client-sfn`, ...) pero **S3 es
  REST-XML → no hay stub** → el handler del provider framework
  (`@aws-sdk/client-s3` external, no bundled) no carga.

Opciones: instalar el SDK real dentro del contenedor ministack (frágil,
node_modules se pierde en recreate) o eliminar el custom resource en deploys
locales. Se eligió la segunda: `autoDeleteObjects` solo importa en `destroy`,
y en local el wipe se hace con `/_ministack/reset` o `docker volume rm`.

### Fix

Mismo patrón que Entrada 6:

1. **`lib/config.ts`** — helper `ConfigHelper.shouldAutoDeleteObjects(scope,
   environmentName)`: default = comportamiento anterior (`!== 'prod'`),
   desactivable con `-c autoDeleteObjects=false`.
2. **`lib/s3-construct.ts`** (2 buckets), **`lib/catalog-construct.ts`**,
   **`lib/web-construct.ts`** — usan el helper.
3. **`deploy-localstack.sh`** — `-c autoDeleteObjects=false` añadido.

### Verificación

- `npm run build` ✅
- `cdk synth -c createAirflowUser=false -c autoDeleteObjects=false` →
  0 recursos `Custom::`
- `cdk synth` default → custom resources presentes (AWS sin cambios)
- `npm test` → 4/4 ✅

---

## Entrada 9: Gate `createAnalyticsResources` — Glue/Athena fuera de CFN

### Síntoma

```
CREATE_FAILED | AWS::Athena::WorkGroup | Unsupported resource type
```

### Root cause y auditoría completa

Para cortar el whack-a-mole se cruzó el template sintetizado completo contra la
lista de provisioners de MiniStack (`services/cloudformation/provisioners.py`):

| Recurso en template | MiniStack CFN |
|---|---|
| Lambda::Function, IAM::Role/ManagedPolicy, S3::Bucket, CDK::Metadata, SSM::Parameter::Value | ✅ |
| AWS::Athena::WorkGroup (1) | ❌ (API Athena sí soporta `CreateWorkGroup`) |
| AWS::Glue::Database (1) | ❌ (API Glue sí soporta `CreateDatabase`) |
| AWS::Glue::Table (5) | ❌ (API Glue sí soporta `CreateTable`) |

Los 3 tipos no soportados tienen API equivalente en MiniStack → se crean por
CLI post-deploy en vez de CFN.

### Fix

1. **`infrastructure-stack.ts`** — flag `createAnalyticsResources` (default
   `true`): cuando es `false`, no se instancian `AnalyticsConstruct` ni
   `GlueConstruct`; dependencias cross-construct condicionadas. AWS real sin
   cambios.
2. **`infrastructure/post-deploy-ministack.sh`** (nuevo) — crea vía
   `aws --endpoint-url=http://localhost:4566`:
   - Athena workgroup `catalunya-workgroup-dev` (misma config que el CDK:
     results bucket, 1GB cutoff, metrics).
   - Glue database `catalunya_data_dev` (mismos parámetros).
   - Las 5 Glue tables (`social_services`, `municipal_population`,
     `municipals`, `service_type`, `service_qualification`) — JSON espejo de
     `lib/glue-construct.ts`.
3. **`deploy-localstack.sh`** — `-c createAnalyticsResources=false` + llamada
   al post-deploy script tras el `cdklocal deploy`.

### Verificación

- Synth con los 3 gates: solo tipos soportados (IAM Role/ManagedPolicy,
  Lambda::Function, S3::Bucket, CDK::Metadata, SSM::Parameter::Value).
- `npm test` → 4/4 ✅
- **Deuda:** las definiciones de tablas quedan duplicadas
  (`glue-construct.ts` ↔ `post-deploy-ministack.sh`). Si cambia una, tocar la
  otra. Alternativa futura: generar el JSON de tablas desde el CDK synth.

---

## Entrada 10: Validación post-deploy — 3 falsos negativos + 2 bugs reales

El deploy CFN completó, pero `validate_deployment` reportaba 3 warnings.
Análisis uno a uno:

### 10.1 "Expected 2 Lambda functions, found: 0" / "No S3 buckets found" — falso negativo

**Causa:** `docker exec cloudgentgran-ministack aws ...` no hereda
credenciales ni región (la imagen no define `AWS_*`; los init scripts los
reciben, `docker exec` no). MiniStack 1.4+ **aísla estado por región** (SigV4
scope) → sin `AWS_DEFAULT_REGION=eu-west-1` consultaba us-east-1 (vacío).
Verificado desde host: deploy real OK (10 lambdas, 5 buckets).

**Fix:** el validador pasa `-e AWS_ACCESS_KEY_ID=test -e AWS_SECRET_ACCESS_KEY=test
-e AWS_DEFAULT_REGION=eu-west-1` al `docker exec`.

### 10.2 "Airflow connection test failed" — 2 bugs reales en cadena

1. **Airflow 3 deshabilita connection tests por defecto** →
   `AIRFLOW__CORE__TEST_CONNECTION: 'Enabled'` en `x-airflow-common`.
2. **La conexión nunca se creó.** Cadena de causas en `airflow-init`:
   - `ModuleNotFoundError: No module named 'airflow'`: la imagen instala
     Airflow con `pip --user` como usuario `airflow`
     (`/home/airflow/.local`), pero init corre como root → user-site no
     resuelve. Fix: `HOME: /home/airflow` en el environment de airflow-init.
   - Tras arreglar eso: `ValueError: Fernet key must be 32 url-safe
     base64-encoded bytes` — el default del compose (`YourFernetKeyHere`)
     no es válido, y `start-local-dev.sh` generaba una key **nueva en cada
     ejecución** sin persistirla (cada full-deploy invalidaba las conexiones
     cifradas en la DB de Airflow).

**Fix:** `set_environment()` en `start-local-dev.sh` ahora carga `.env` si
existe y persiste las keys generadas (compose lee `.env` automáticamente;
`.env` ya está en `.gitignore`).

### Verificación

- `airflow connections test localstack_default` → **Connection success!** ✅

---

## Trabajo pendiente (próximas entradas)

| Archivo | Cambio necesario |
|---|---|
| `orchestration/dags/*.py` (5 DAGs) | Renombrar `aws_conn_id: localstack_default` → `ministack_default` (opcional, limpieza) |
| `orchestration/plugins/operators/dbt_athena_operator.py:137` | Default `http://localstack:4566` → `http://ministack:4566` |
| `scripts/start-local-dev.sh` | ~~Health checks y volumen de estado~~ ✅ Migrado (Entrada 4) |
| `scripts/localstack-s3-backup.sh` | Health check, perfil `localstack` y nombre; restaurar `localstack/s3-backup/` en buckets MiniStack |
| `infrastructure/deploy-localstack.sh` | Revisar `cdklocal` contra MiniStack; renombrar / parametrizar endpoint (Entrada 4, fuera de alcance) |
| `docs/rust_lambda_builds.md`, `scripts/test-act.sh` | ~~Perfil/health LocalStack~~ ✅ Migrados (Entrada 5) |
| `localstack/volume` | Formato incompatible con MiniStack; archivar o borrar tras validar la migración |
| `docs/`, `orchestration/README.md` | Referencias a LocalStack |

## Verificación (checklist)

- [ ] `docker compose -f docker-compose.local.yaml up -d` levanta `ministack` healthy en < 30 s
- [ ] `curl http://localhost:4566/_ministack/health` responde
- [ ] `aws --endpoint-url=http://localhost:4566 s3 ls` funciona
- [ ] Airflow connection test `localstack_default` OK
- [ ] Restaurar backups S3 desde `localstack/s3-backup/`
- [ ] `DbtAthenaOperator` ejecuta SQL real contra Athena (DuckDB, imagen `:full`)
- [ ] Lambda Rust (`provided.al2023`) invoca en contenedor Docker
