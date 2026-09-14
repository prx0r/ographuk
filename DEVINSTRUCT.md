Yes. This should become a first-class layer of the system.

The key idea is bigger than “UK business graph.” It is a continuously improving **Oracle**:

$$
\boxed{
\text{world data}
\rightarrow
\text{verified observations}
\rightarrow
\text{entities + relationships}
\rightarrow
\text{signals}
\rightarrow
\text{candidate opportunities}
\rightarrow
\text{Seesaw}
\rightarrow
\text{products/trades/campaigns}
\rightarrow
\text{real outcomes}
\rightarrow
\text{better Oracle}
}
$$

`cgraphuk` already has an excellent ontology seed—24 vertical templates, pain graphs, legislation, tools, campaigns and explicit graph namespaces—but almost no real company population yet. `/bq` confirms the same thing from the data side: only 4,307 live rows, 454 knowledge nodes, 466 edges, and `COMP_*` is effectively absent.

That tells me exactly where to go next: **stop expanding the hand-written ontology and start filling it with reality.**

One especially useful frontier development: **BigQuery Graph became GA on September 1, 2026**, with native property graphs and GQL alongside SQL. We do not need Neo4j/Spanner/etc. right now; your existing BQ can become the graph engine. ([Google Cloud][1])

Here is the full brief I'd give the other agent.

# Oracle UK

## Mission

Build the canonical continually updating information graph for the UK.

The system must turn heterogeneous public, commercial and proprietary observations into a temporally versioned, provenance-preserving graph that can support:

```text
Seesaw investment/business allocation
AgentCom autonomous builds
ChatGPT plugin discovery
UK business opportunities
BreadUp product/resale intelligence
advertising strategy
trading theses
market research
lead generation where legally/permissibly allowed
regulatory/compliance products
future autonomous businesses
```

Do not optimize initially for a pretty graph UI.

Optimize for:

> **How much useful, attributable, queryable reality can the system accumulate?**

---

# 1. Canonical architecture

Use existing repositories.

Do NOT create another graph repo yet.

```text
prx0r/cgraphuk
=
Oracle UK semantics + ingestion + entity resolution + signals

prx0r/bq
=
BigQuery schema/state/catalog + queries/views/property graph

prx0r/agentcomfinal
=
consumer of opportunities and producer of real outcomes
```

Canonical loop:

```text
                    EXTERNAL WORLD
                          │
                    source adapters
                          │
                          ▼
                    RAW EVIDENCE
                          │
                          ▼
                     NORMALIZER
                          │
                          ▼
                  IDENTITY RESOLVER
                          │
                          ▼
                 ┌─────────────────┐
                 │  ORACLE FACTS   │
                 │                 │
                 │ entities        │
                 │ observations    │
                 │ relationships   │
                 │ events          │
                 └────────┬────────┘
                          │
                          ▼
                  BIGQUERY GRAPH
                          │
              ┌───────────┼────────────┐
              ▼           ▼            ▼
           signals      slices       changes
              │
              ▼
               OPPORTUNITY DETECTORS
                          │
                          ▼
                  candidate hypotheses
                          │
                          ▼
                       SEESAW
                          │
            BUILD / TRADE / WATCH / DROP
                          │
                          ▼
                      AGENTCOM
                          │
                real products/actions
                          │
                          ▼
                      outcomes
                          │
                          └──────────────→ ORACLE
```

Oracle observes.

Seesaw interprets economically.

AgentCom acts.

QP verifies consequential outcomes.

Do not collapse these responsibilities.

---

# 2. Fix the current ingestion philosophy

Current `ingestion-pipeline.md` says:

> “Raw payloads are never stored.”

Reverse this.

For an Oracle, raw evidence is valuable.

Use:

```text
SOURCE
  ↓
immutable raw object
  ↓
hash
  ↓
normalization
  ↓
facts
```

Raw source payloads allow:

```text
parser replay
schema-drift repair
new feature extraction later
audit
provenance verification
LLM re-extraction with future better models
```

Do not put giant raw blobs in normal BQ fact tables.

Use a cheap raw landing layer:

```text
raw/<source>/<date>/<sha256>.<format>
```

GCS is natural given the existing BQ stack, but filesystem storage is acceptable in development.

BQ stores:

```text
raw_uri
raw_sha256
parser_version
```

not necessarily the entire payload.

---

# 3. Three distinct epistemic layers

Never mix these.

## Layer 1 — observations

Things a source actually said.

Example:

```json
{
  "subject": "COMP_01234567",
  "predicate": "company.status",
  "value": "active",
  "source": "companies-house",
  "observed_at": "...",
  "raw_sha256": "..."
}
```

## Layer 2 — derived signals

Mechanical transformations.

Example:

```text
accounts_due_days = accounts_due_date - today
```

or:

```text
local_competitor_density =
count(companies matching SIC within 5km)
```

Every derived signal stores:

```text
formula_id
formula_version
input observation IDs
```

## Layer 3 — hypotheses/opportunities

Interpretations such as:

> “Manchester electricians may have unusually high demand relative to supply.”

These are never facts.

Store separately as:

```text
HYPOTHESIS
OPPORTUNITY
PREDICTION
```

with supporting and contradicting evidence.

This mirrors QP's:

$$
Evidence \neq Inference
$$

---

# 4. Do not use verification as one overloaded flag

Current `cgraphuk` uses:

```text
PROPOSED
VERIFIED
REJECTED
```

and currently has known mechanical/fail-open verification problems.

Replace the conceptual model with explicit fields:

```text
source_class:
    primary-government
    primary-commercial
    secondary
    user
    model-derived

observation_status:
    OBSERVED
    INVALID
    SUPERSEDED

derivation_status:
    DERIVED

confidence:
    numeric / null

verification_ref:
    optional QP/evidence receipt

basis:
    exact source reference
```

Government does not mean infallible.

It means authoritative for a defined field.

---

# 5. Canonical Oracle data model

Do NOT continue generating dozens of domain-specific empty tables.

`/bq` currently has approximately 45 schema-only tables that have never received data.

Collapse the live Oracle around a small generic spine.

Recommended canonical tables:

```text
oracle_sources
oracle_ingest_runs
oracle_raw_objects

oracle_entities
oracle_identifiers
oracle_relations

oracle_observations
oracle_events

oracle_signals
oracle_hypotheses
oracle_outcomes
```

Domain-specific SQL should generally be views.

---

# 6. Entity

Canonical shape:

```json
{
  "entity_id": "COMP_01234567",
  "entity_type": "company",
  "country": "GB",
  "created_at": "...",
  "canonical_name": "...",
  "status": "active"
}
```

Initial entity classes:

```text
company
business_location
property
postcode
local_authority
industry
occupation
person_role
brand

product
product_category
marketplace_listing

government_body
contracting_authority
public_contract

regulation
licence
permit

advertiser
ad
creative
keyword
trend

website
domain
software_tool

opportunity
campaign
product_build
```

Avoid creating a separate table for each.

---

# 7. Identifiers are first-class objects

This is essential.

Example:

```text
COMP_01234567

HAS_IDENTIFIER
→ companies_house_number:01234567

HAS_LOCATION
→ LOC_...

location:
  postcode
  UPRN
  latitude
  longitude

HAS_IDENTIFIER
→ CQC_LOCATION_ID
→ FHRS_ID
→ charity_number
→ OSM_ID
```

The most useful UK identifiers include:

```text
Companies House number
UPRN
postcode
local authority code
SIC
charity number
CQC provider/location ID
FHRS establishment ID
OCID procurement ID
EPC certificate/property reference
OSM element ID
GTIN
MPN
eBay item ID
domain
```

OS Open UPRN alone contains coordinates for roughly 40 million addressable GB locations and is free to use, so UPRN should eventually become a major location-join key. ([Ordnance Survey][2])

Do not ingest all 40 million rows on day one unless useful.

Adopt UPRNs opportunistically first.

---

# 8. Entity resolution

Current `ALIGNMENT.md` says:

> exact-match, no fuzzy joins.

Keep that rule **for canonical identity**.

But add candidate resolution.

Example:

```text
COMP_123
      ↕
SAME_AS_CANDIDATE
      ↕
OSM_NODE_555
```

Candidate edge contains:

```text
confidence
method
evidence
```

Methods:

```text
exact company number                  → automatic
exact UPRN                            → automatic
exact regulatory ID                   → automatic

domain + postcode                     → candidate
name + postcode                       → candidate
name + phone                          → candidate
name + geo proximity + SIC            → candidate
```

Only promote to:

```text
SAME_AS
```

after a deterministic threshold + evidence rule or human/QP verification.

Thus:

```text
no fuzzy joins in truth
```

without throwing away entity resolution.

---

# 9. Make the graph temporal

Everything interesting is a change.

Every observation should carry:

```text
observed_at
valid_from
valid_to
ingested_at
```

This gives us:

```text
what is true now?
what was true on date X?
what changed?
how quickly is it changing?
```

Do not overwrite:

```text
rating = 4
```

with:

```text
rating = 3
```

Store:

```text
rating 4 @ T1
rating 3 @ T2
```

and generate:

```text
EVENT:
FOOD_RATING_DROPPED
```

The change itself is often the alpha.

---

# 10. BigQuery Graph

Do not install another graph database yet.

BigQuery Graph became generally available on September 1, 2026 and provides native graph modelling/traversal with GQL while retaining normal SQL/BigQuery analytics. ([Google Cloud][1])

Create a property graph over:

```text
oracle_entities
oracle_relations
```

while observations/signals remain joinable BQ tables.

Target:

```sql
GRAPH_TABLE(
  oracle_uk
  MATCH
    (company:Company)-[:OPERATES_AT]->(loc:Location)
    <-[:OPERATES_AT]-(competitor:Company)
  ...
)
```

Use SQL for aggregates.

Use GQL for relationships.

Do not migrate to Spanner unless real transactional graph requirements appear.

---

# 11. Source Registry v2

Promote the existing blueprint registry into executable configuration.

Each source gets:

```json
{
  "source_id": "companies-house",

  "jurisdiction": "GB",

  "access": "bulk+api+stream",

  "auth_class": "KEY",

  "cost": 0,

  "license": "...",

  "allowed_uses": [],

  "prohibited_uses": [],

  "cadence": "stream",

  "entity_keys": [
    "company_number"
  ],

  "raw_retention": true,

  "adapter": "...",

  "parser_version": "...",

  "last_success": "...",

  "cursor": "...",

  "schema_hash": "..."
}
```

Every source adapter must pass the same interface.

---

# 12. Priority source: Companies House

This should become the company backbone.

Do not rely solely on per-company API requests.

Companies House provides a free monthly bulk snapshot of live companies; the September 1, 2026 snapshot is approximately 469 MB compressed. It also offers free bulk accounts files and a PSC data product. ([GOV.UK][3])

Use:

```text
monthly bulk snapshot
        ↓
full reconciliation
```

plus:

```text
Streaming API
        ↓
incremental change events
```

The streaming API emits realtime company changes. ([Company Information Developer Specs][4])

Initial company graph:

```text
COMPANY
 ├─ SIC
 ├─ address
 ├─ incorporation date
 ├─ company status
 ├─ accounts dates
 ├─ confirmation dates
 ├─ previous names
 ├─ officers
 ├─ PSC
 ├─ charges
 ├─ filing history
 └─ insolvency
```

Then extract electronically filed accounts from Companies House iXBRL.

Useful financial observations:

```text
revenue
gross profit
operating profit
cash
current assets
current liabilities
debt
net assets
employee count
```

Always retain:

```text
taxonomy concept
filing
period
parser version
```

because accounts vary.

---

# 13. High-priority government sources

After Companies House, implement sources in roughly this order.

### ONS / Nomis

Use for:

```text
business populations
business births/deaths
employment
vacancies
occupation
local authority activity
SIC density
turnover bands
```

ONS data goes down to local authority and detailed SIC in multiple datasets. ([Office for National Statistics][5])

This answers:

> Is an apparent company cluster actually large relative to the local economy?

---

### Food Standards Agency FHRS

Free, keyless API with live geocoded food-business records across the UK. ([Food Standards Agency][6])

Excellent real-business graph.

Nodes:

```text
restaurant
hotel
takeaway
retailer
care establishment
```

Signals:

```text
rating
rating change
inspection date
local density
low-rating concentration
```

---

### CQC

Daily-updated API plus downloadable care directories covering providers and locations, including registration, regulated activities, service type and ratings. ([Care Quality Commission][7])

This is an extraordinarily good vertical-specific graph for AgentCom.

---

### Contracts Finder + Find a Tender

Both publish OCDS data/APIs. ([GOV.UK][8])

Model:

```text
CONTRACTING_AUTHORITY
       ↓ publishes
PROCUREMENT
       ↓ awarded_to
COMPANY
```

Signals:

```text
contract value
category
region
award frequency
supplier concentration
repeat winner
new opportunity
```

This alone can generate businesses:

> “SMEs like X repeatedly win £Y contracts in region Z.”

---

### Planning Data

Planning Data now exposes more than 100 England planning/housing datasets through one API, including planning applications, listed buildings, conservation areas, brownfield land and other constraints. ([Planning Data][9])

Connect:

```text
PROPERTY/LOCATION
  ↓
planning applications
constraints
nearby development
```

Extremely relevant to:

```text
builders
electricians
HVAC
solar
EV
property services
```

---

### Land Registry

Price Paid Data gives sale transactions across England and Wales, monthly, under OGL; the current publication also provides a UPRN lookup table. ([GOV.UK][10])

This is a powerful bridge:

```text
PROPERTY
→ sale
→ UPRN
→ postcode
→ planning
→ EPC
→ local businesses
```

---

### EPC

The government's energy-performance data service provides bulk domestic, non-domestic and display certificate data plus a developer API. ([Energy Performance Data][11])

Excellent for:

```text
retrofit
heat pumps
insulation
solar
building efficiency
commercial energy
```

---

### Gazette / insolvency

The Gazette exposes linked data including JSON-LD/RDF/XML plus SPARQL access to official notices. ([The Gazette][12])

Insolvency Service publishes monthly company insolvency data including industry breakdowns. ([GOV.UK][13])

Generate events:

```text
COMPANY_DISTRESS
INSOLVENCY
LIQUIDATION
CREDITOR_NOTICE
```

Potential BreadUp consequence:

```text
business liquidation
→ assets may enter secondary market
```

---

### Environment Agency

Public Registers expose environmental permits, licences, exemptions, waste carriers, scrap-metal dealers and compliance reports. ([Defra Data Services][14])

This becomes valuable for industrial/service verticals.

---

### DVLA/DfT

Detailed downloadable vehicle files exist, including make/model/geography, with quarterly/annual updates. ([GOV.UK][15])

This can drive:

```text
garage opportunities
EV servicing
charger deployment
parts demand
fleet services
```

---

### Ofcom

Ofcom publishes infrastructure/coverage datasets, including mobile measurement data and broadband availability reports. ([www.ofcom.org.uk][16])

Useful location feature:

```text
connectivity_quality
```

for:

```text
remote businesses
property
hospitality
home offices
telecom sales
```

---

# 14. Commercial-demand graph

Government data tells us what exists.

We also need:

> What do people want?

Create:

```text
DEMAND_SIGNAL
```

with:

```text
topic
product
category
location
channel
value
growth
observed_at
```

---

# 15. Pinterest

Pinterest now has a Trends API with growing/monthly/yearly/seasonal keyword rankings and growth rates; GB+IE is a supported region. Importantly, its API only exposes current trends rather than historical dates. ([Pinterest Developers][17])

That means:

$$
\boxed{\text{daily snapshots create proprietary history}}
$$

Run every day.

Store:

```text
keyword
rank
WoW
MoM
YoY
interest
age
gender
date
```

After a year, we own a time series Pinterest itself does not expose through the API.

That is exactly the kind of graph moat we want.

---

# 16. Meta Ad Library

The Ad Library API permits searches for any type of ad delivered to the UK/EU during the previous year, with creative/page/delivery metadata. ([Facebook][18])

Graph:

```text
ADVERTISER
   ↓ RUNS
AD
   ↓ LINKS_TO
LANDING_PAGE
   ↓ SELLS
PRODUCT/SERVICE
```

Daily snapshot:

```text
new creatives
creative longevity
creative variants
advertiser activity
landing pages
category clusters
```

This produces a unique historical ad-strategy graph.

---

# 17. TikTok

TikTok Creative Centre is free and public and includes high-performing ads, trends, keywords and products. ([TikTok For Business][19])

Start with low-volume compliant snapshots.

Do not build a brittle scraping farm initially.

Record:

```text
brand
industry
region
creative URL/id
likes
CTR band
budget band
caption
landing page
date
```

---

# 18. eBay and BreadUp

There is a nuance.

eBay gives sellers **Product Research** free access to three years of actual sold-price and sales data, including:

```text
actual sold price
average price
price range
sell-through
seller count
postage
```

([eBay UK][20])

But the official Marketplace Insights API that exposes sales history remains limited-release. ([eBay Developers][21])

Therefore do NOT architect Oracle around an imaginary unrestricted sold-data API.

Use a hierarchy:

```text
1. user-authorized own sales/outcomes
2. permitted Product Research snapshots
3. eBay active inventory via Browse API
4. per-listing QuantitySold where available
5. eventually Marketplace Insights if access obtained
```

The Trading API exposes lifetime `QuantitySold` for individual listings. ([eBay Developers][22])

BreadUp should ultimately contribute the strongest data itself:

```text
identified item
→ estimated value
→ listing
→ clicks
→ offers
→ sold price
→ time-to-sale
→ fees
→ realized margin
```

That proprietary realized-outcome graph will be more defensible than scraped eBay data.

---

# 19. Product graph

Introduce:

```text
PRODUCT
BRAND
CATEGORY
LISTING
SALE_OBSERVATION
PRICE_OBSERVATION
```

Relations:

```text
LISTING —LISTS→ PRODUCT
PRODUCT —BRANDED_BY→ BRAND
PRODUCT —IN_CATEGORY→ CATEGORY
LISTING —ON_MARKETPLACE→ MARKETPLACE
SALE —OF→ PRODUCT
```

Then BreadUp query:

```text
product
→ current supply
→ historical sales
→ price distribution
→ sell-through
→ local availability
→ shipping
→ realized BreadUp outcomes
```

---

# 20. Advertising Opportunity Graph

Combine:

```text
Pinterest demand
+
TikTok creatives
+
Meta advertising
+
eBay sales
+
company density
```

to detect things such as:

```text
consumer interest rising
AND
seller count low
AND
few advertisers
AND
healthy price/margin
```

That becomes:

```text
OPPORTUNITY:
possible product/ad campaign
```

not a fact.

---

# 21. Deterministic signal library

Do not begin with LLM-generated scores.

Build versioned transforms.

Examples:

```text
local_company_density

business_birth_rate
business_death_rate

procurement_growth
supplier_concentration

rating_decline_rate

price_dispersion
sell_through_rate

ad_creation_velocity
advertiser_count

trend_acceleration

regulatory_exposure

property_transaction_velocity

planning_activity

EPC_improvement_gap
```

Each:

```json
{
  "signal_id": "...",
  "formula_version": "v1",
  "inputs": [],
  "value": 0.0,
  "computed_at": "..."
}
```

---

# 22. Opportunity detectors

Do not ask an LLM:

> “Find good ideas.”

Give it structural candidates.

Mechanical detectors:

### Supply gap

```text
demand ↑
supply flat/down
```

### Fragmentation

```text
many tiny providers
+
no dominant software/marketplace
```

### Regulation shock

```text
new rule
×
number of exposed businesses
```

### Price inefficiency

```text
large price dispersion
+
healthy transaction volume
```

### Geographic hole

```text
demand proxy high
+
provider density low
```

### Tech weakness

```text
large business population
+
poor digital stack penetration
```

### Advertising gap

```text
search/social trend accelerating
+
advertiser density low
```

### Procurement wedge

```text
repeated public spend
+
low supplier concentration / emerging category
```

Each emits:

```text
CandidateOpportunity
```

---

# 23. CandidateOpportunity schema

```json
{
  "opportunity_id": "...",

  "subject": "...",

  "type": "BUSINESS|PLUGIN|TRADE|AD|PRODUCT",

  "thesis": "...",

  "supporting_signals": [],

  "contradicting_signals": [],

  "unknowns": [],

  "affected_entities": [],

  "estimated_market_surface": {},

  "possible_moat": [],

  "suggested_probe": [],

  "falsifiers": [],

  "created_at": "..."
}
```

The Oracle does **not** decide BUILD.

Seesaw does.

---

# 24. Seesaw export

Create:

```bash
oracle seesaw export
```

Output feature vectors, not prose.

Example:

```json
{
  "opportunity": "opp-...",

  "demand_change": 0.82,
  "supply_constraint": 0.61,
  "fragmentation": 0.91,
  "price_dispersion": 0.44,

  "regulatory_pressure": 0.72,

  "software_commoditization_risk": 0.31,

  "external_state_moat": 0.78,

  "authority_moat": 0.56,

  "data_accumulation_potential": 0.94,

  "unknowns": [...]
}
```

Seesaw can then apply its own current economic model.

Do not hardwire Seesaw's score into Oracle.

---

# 25. Information acquisition loop

This is one of the highest-value components.

When an opportunity is promising but uncertain, Oracle should ask:

> What observation would most change the decision?

Create:

```text
DataGap
```

and:

```text
ProbeRequest
```

Example:

```json
{
  "question":
    "Is there actually excess demand for electricians in Bristol?",

  "decision":
    "BUILD trade-lead plugin",

  "known": [],

  "unknown": "real request volume",

  "possible_sources": [
    "Google/Pinterest trend",
    "job/vacancy data",
    "quote marketplace observation"
  ],

  "expected_information_gain": 0.71,

  "cost": 0.02
}
```

Basic scheduler:

$$
ProbePriority =
\frac{
DecisionValue
\times
ProbabilityDecisionChanges
\times
InformationGain
}{
1+Cost
}
$$

This is the data equivalent of Autobuild.

The Oracle itself learns what to observe next.

---

# 26. Outcome feedback

This is the moat.

Suppose Oracle says:

```text
"barbers need missed-call automation"
```

AgentCom builds it.

Then record:

```text
leads contacted
businesses onboarded
calls answered
appointments created
conversion
revenue
churn
```

Back into Oracle.

Now the graph contains not only:

```text
things found online
```

but:

```text
what happened when we acted on them
```

That becomes proprietary.

---

# 27. Downstream product surfaces

Oracle should eventually power things such as:

### ChatGPT UK Business Intelligence plugin

```text
"Find care homes near Manchester with recent poor ratings."
```

### UK procurement plugin

```text
"What live government opportunities fit a 5-person electrical contractor?"
```

### AgentCom lead generator

```text
business pain
+
location
+
company status
+
digital weakness
→ target
```

### BreadUp

```text
"What's underpriced locally and liquid online?"
```

### Retrofit / energy opportunity engine

```text
EPC
+
property
+
planning
+
business providers
+
energy signals
```

### Ad campaign generator

```text
trend
+
competitor ads
+
product economics
→ candidate campaign
```

### Seesaw trading research

```text
regulation
→ industry
→ company
→ inputs
→ suppliers
→ observed changes
→ thesis/falsifier
```

---

# 28. Oracle MCP

Expose a very small surface.

```text
oracle.entity
oracle.search
oracle.slice
oracle.changes
oracle.evidence
oracle.opportunities
oracle.signal
```

Examples:

```text
oracle.entity(company_number)

oracle.slice(
  type="company",
  sic="43210",
  location="Manchester"
)

oracle.changes(
  entity_type="restaurant",
  change="rating_drop",
  since="7d"
)

oracle.opportunities(
  type="plugin",
  vertical="care"
)
```

AgentCom should never need to understand BQ table layout.

---

# 29. Provenance must always be inspectable

Every answer must support:

```text
WHY DO WE THINK THIS?
```

Query:

```text
oracle.evidence(signal_id)
```

returns:

```text
signal
→ formula
→ observations
→ source records
→ raw hashes
```

This is essential for Seesaw and trading.

---

# 30. Build first-party history where APIs expose only current state

This is strategically important.

Whenever an external source exposes:

```text
current snapshot
```

but not historical data:

**snapshot it ourselves.**

Examples:

```text
Pinterest trends
TikTok top ads
Meta ads
active eBay inventory
OSM business listings
public prices
website technology
```

Over time:

$$
\text{public present-state API}
\rightarrow
\boxed{\text{our proprietary historical dataset}}
$$

That is real data accumulation.

---

# 31. Data-rights gate

Every source registry entry requires:

```text
licence
storage rights
commercial reuse rights
attribution
API terms
retention restrictions
```

For example, Google Business Profile APIs should **not** be used as a general lead-generation data source: Google explicitly limits them to businesses you own/are authorised to manage and restricts storing/aggregating API content. ([Google for Developers][23])

Use GBP later for **authorized customer management**.

Use:

```text
Companies House
FSA
CQC
OSM
government data
```

for discovery.

---

# 32. Repo restructuring

Promote `cgraphuk` from “copy mirror” into the Oracle semantic owner.

Current README still says many files are copies whose masters live elsewhere.

That guarantees drift.

Target:

```text
cgraphuk/
│
├── oracle/
│   ├── ids.py
│   ├── contracts.py
│   ├── provenance.py
│   │
│   ├── sources/
│   │   ├── registry.py
│   │   ├── companies_house.py
│   │   ├── ons.py
│   │   ├── fhrs.py
│   │   ├── cqc.py
│   │   ├── procurement.py
│   │   ├── planning.py
│   │   ├── land_registry.py
│   │   └── ...
│   │
│   ├── normalize/
│   ├── resolve/
│   ├── signals/
│   ├── opportunities/
│   ├── probes/
│   │
│   ├── exports/
│   │   ├── seesaw.py
│   │   ├── agentcom.py
│   │   └── breadup.py
│   │
│   └── mcp/
│
├── schemas/
├── sources/
├── sql/
├── fixtures/
├── tests/
│
└── legacy/
    └── current templates/pain docs
```

Do not delete the ontology.

Demote static copies to `legacy/reference` as the runtime becomes canonical.

---

# 33. `/bq` target

`/bq` becomes:

```text
bq/
├── schema/
│   ├── 001_oracle_core.sql
│   └── ...
│
├── graph/
│   └── oracle_uk.sql
│
├── views/
│   ├── companies.sql
│   ├── local_markets.sql
│   ├── product_markets.sql
│   ├── changes.sql
│   └── ...
│
├── queries/
├── snapshots/
└── generated/
    ├── CATALOG.md
    └── TABLE_STATUS.md
```

Generated documentation stays useful.

Semantic logic stays in `cgraphuk`.

---

# 34. Phase roadmap

## E0 — Oracle contract

DONE when:

```text
source
raw object
entity
identifier
relation
observation
event
signal
hypothesis
outcome
```

all have schemas and content-derived IDs.

---

## E1 — raw/provenance pipeline

Implement:

```text
fetch
→ raw snapshot
→ hash
→ ingest receipt
→ normalization
```

Hard acceptance:

```text
same payload → same raw hash
parser can replay from raw snapshot
no observation lacks provenance
```

---

## E2 — company spine

Ingest Companies House bulk snapshot.

DONE when:

```text
millions of current UK companies
```

are queryable by:

```text
company number
name
SIC
postcode
status
incorporation date
```

Then attach the streaming feed.

---

## E3 — geography spine

Add:

```text
postcode
local authority
lat/lon
UPRN where available
```

Hard acceptance:

```text
company → location → local authority
```

works for a meaningful majority of companies.

---

## E4 — first cross-source joins

Add:

```text
FSA
CQC
Contracts Finder / Find a Tender
```

DONE when Oracle can answer:

```text
"Show all identifiable companies linked to at least two independent sources."
```

---

## E5 — physical-property graph

Add:

```text
Land Registry
Planning Data
EPC
```

DONE when:

```text
location/property
→ sale
→ EPC
→ planning context
→ nearby providers
```

is queryable.

---

## E6 — change engine

Every update produces events.

Examples:

```text
NEW_COMPANY
DIRECTOR_CHANGED
NEW_PROCUREMENT
CONTRACT_AWARDED
RATING_DROPPED
PLANNING_APPLICATION
PRICE_CHANGED
NEW_AD
TREND_ACCELERATED
```

Hard acceptance:

```text
oracle changes --since 24h
```

returns useful real changes.

---

## E7 — market/demand graph

Add:

```text
Pinterest
Meta
TikTok
eBay
```

Start daily snapshots.

Do not wait for perfect historical access.

---

## E8 — Seesaw feed

Implement:

```bash
oracle seesaw export
```

with feature vectors + evidence refs.

No LLM narrative required.

---

## E9 — opportunity engine

Implement deterministic detectors.

Generate first:

```text
100 candidate opportunities
```

across:

```text
business
plugin
product
advertising
trading
```

Then Seesaw filters them.

---

## E10 — first downstream proof

Use the graph to produce one actual product decision.

Recommended:

```text
AgentCom UK / ChatGPT business plugin
```

or:

```text
BreadUp product opportunity
```

Build it.

Record actual outcome.

Feed it back.

That closes the system.

---

# 35. Immediate work order

Do these before researching hundreds more sources:

1. Make `cgraphuk` the canonical Oracle semantics owner.
2. Create the generic Oracle schemas.
3. Change raw retention from discard → immutable hash-addressed storage.
4. Create source registry v2 including licensing.
5. Load full Companies House monthly company snapshot.
6. Implement Companies House streaming changes.
7. Build company→postcode→local-authority identity.
8. Add FSA.
9. Add CQC.
10. Add procurement OCDS.
11. Add Planning Data.
12. Add Land Registry + EPC.
13. Define BigQuery `oracle_uk` property graph.
14. Implement temporal change/event generation.
15. Add `oracle.entity`, `.slice`, `.changes`, `.evidence` MCP tools.
16. Add Pinterest/Meta/TikTok/eBay demand snapshots.
17. Build signals.
18. Build opportunity candidates.
19. Export to Seesaw.
20. Send accepted opportunities to AgentCom.

Do not add fifty more empty BigQuery tables.

Every schema should be justified by live data.

---

# 36. Terminal endstate

The system is working when this is possible:

```text
USER / AGENT:

"What is weirdly underserved in Birmingham right now?"

         ↓

Oracle:
Companies House density
ONS business/employment
FSA/CQC
planning
procurement
ads
trends
marketplace activity
historical changes

         ↓

returns:
5 structural anomalies
with exact evidence

         ↓

Seesaw:
evaluates scarcity/moat

         ↓

candidate:
"X looks unusually attractive because..."

         ↓

AgentCom:
compile actual product/plugin/business

         ↓

deploy

         ↓

real users/revenue/conversion

         ↓

Oracle records outcome

         ↓

future opportunity model improves
```

And similarly:

```text
"What should BreadUp tell someone to buy today?"

"What ChatGPT plugin should we build next?"

"What UK regulation just created an opportunity?"

"Which vertical is getting materially worse at fulfilling demand?"

"Which ad category is accelerating before seller supply catches up?"

"Which company/sector appears exposed to a changing constraint?"

"What information would most reduce uncertainty on this thesis?"
```

The long-term moat is not the graph software.

It is:

$$
\boxed{
\text{years of normalized UK reality}
+
\text{historical snapshots}
+
\text{cross-source identity}
+
\text{our own action/outcome data}
}
$$

Public data creates the initial graph.

Products create the proprietary graph.

The most exciting immediate source is actually **Companies House bulk + stream**: you can seed essentially the UK corporate spine cheaply from a free 469 MB monthly snapshot, then maintain it from the realtime stream, and later enrich it with bulk accounts and PSC ownership data. ([GOV.UK][3])

And the “record public current data to create private historical data” idea is particularly strong for Pinterest: its current Trends API explicitly does **not** provide past-date retrieval, so a daily Oracle capture creates a historical asset unavailable through that API later. ([Pinterest Developers][17])

This makes `/cgraphuk + /bq` potentially much more strategically important than another application: **the applications become sensors feeding the Oracle, and the Oracle generates the next applications.**

[1]: https://cloud.google.com/blog/products/data-analytics/bigquery-graph-connecting-data-and-ai-at-scale/?utm_source=chatgpt.com "BigQuery Graph: Connecting Data and AI at Scale | Google Cloud Blog"
[2]: https://www.ordnancesurvey.co.uk/products/os-open-uprn?utm_source=chatgpt.com "OS Open UPRN | Data Products | OS"
[3]: https://www.gov.uk/guidance/companies-house-data-products?utm_source=chatgpt.com "Companies House data products - GOV.UK"
[4]: https://developer-specs.company-information.service.gov.uk/streaming-api/guides/overview "https://developer-specs.company-information.service.gov.uk/streaming-api/guides/overview"
[5]: https://www.ons.gov.uk/businessindustryandtrade/business/activitysizeandlocation "https://www.ons.gov.uk/businessindustryandtrade/business/activitysizeandlocation"
[6]: https://api.ratings.food.gov.uk/help "https://api.ratings.food.gov.uk/help"
[7]: https://www.cqc.org.uk/about-us/transparency/using-cqc-data "https://www.cqc.org.uk/about-us/transparency/using-cqc-data"
[8]: https://www.gov.uk/government/publications/open-contracting "https://www.gov.uk/government/publications/open-contracting"
[9]: https://www.planning.data.gov.uk/docs "https://www.planning.data.gov.uk/docs"
[10]: https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads "https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads"
[11]: https://get-energy-performance-data.communities.gov.uk/ "https://get-energy-performance-data.communities.gov.uk/"
[12]: https://www.thegazette.co.uk/data "https://www.thegazette.co.uk/data"
[13]: https://www.gov.uk/government/statistics/company-insolvencies-july-2026 "https://www.gov.uk/government/statistics/company-insolvencies-july-2026"
[14]: https://environment.data.gov.uk/public-register/view/index "https://environment.data.gov.uk/public-register/view/index"
[15]: https://www.gov.uk/government/statistical-data-sets/vehicle-licensing-statistics-data-files "https://www.gov.uk/government/statistical-data-sets/vehicle-licensing-statistics-data-files"
[16]: https://www.ofcom.org.uk/phones-and-broadband/coverage-and-speeds/mobile-signal-strength-measurement-data?utm_source=chatgpt.com "Mobile signal strength measurement data from our spectrum assurance vehicles"
[17]: https://developer.pinterest.com/docs/analytics-and-reports/trends/ "https://developer.pinterest.com/docs/analytics-and-reports/trends/"
[18]: https://br-fr.facebook.com/ads/library/api/?source=archive-landing-page "https://br-fr.facebook.com/ads/library/api/?source=archive-landing-page"
[19]: https://ads.tiktok.com/resources/help/article/creative-center?lang=en-GB "https://ads.tiktok.com/resources/help/article/creative-center?lang=en-GB"
[20]: https://www.ebay.co.uk/sellercentre/news/2024-june/product-research "https://www.ebay.co.uk/sellercentre/news/2024-june/product-research"
[21]: https://developer.ebay.com/develop/get-started/get-started-on-a-buying-application "https://developer.ebay.com/develop/get-started/get-started-on-a-buying-application"
[22]: https://developer.ebay.com/devzone/xml/docs/Reference/ebay/GetItem.html "https://developer.ebay.com/devzone/xml/docs/Reference/ebay/GetItem.html"
[23]: https://developers.google.com/my-business/content/faq "https://developers.google.com/my-business/content/faq"
