# ENA Automatic Submission System

This system aims to **automate the validation and submission of metadata and sequencing data** to the **European Nucleotide Archive (ENA)**, following the metadata standards defined by the **MIXS specification**.

## Features

* **Metadata validation**:

  * Date format verification (ISO 8601).
  * Expected value checks and unit validation.
  * Controlled vocabulary and ontology validation (e.g., ENVO, CHEBI, NCBI Taxonomy).

* **Automated submission**:

  * Upload of metadata and sequencing data files.
  * Integration with the ENA submission API (planned for future phases).

## Initial Scope

In its initial version, this system supports only **Terrestrial metadata**.

The metadata fields and requirements are based on the MIXS specification and are described below.

---

## Metadata Structure Overview

| Category             | Metadata          | Definition                                                    | Reference                                                         | Expected Value / Unit           | Example                                 |
| -------------------- | ----------------- | ------------------------------------------------------------- | ----------------------------------------------------------------- | ------------------------------- | --------------------------------------- |
| **Project metadata** | `project_name`    | Name of the project within which the sequencing was organized | [MIXS:0000092](https://w3id.org/mixs/0000092)                     | Free text string                | Forest soil metagenome                  |
| **Site metadata**    | `collection_date` | Time of sampling (point or interval). ISO8601 format required | [MIXS:0000011](https://w3id.org/mixs/0000011)                     | YYYY-MM-DD                      | 2013-03-25T12:42:31+01:00               |
|                      | `collected_by`    | Name of person or institute that collected the sample         | [ENA Reference](https://www.ebi.ac.uk/ena/browser/view/ERC000043) | Free text string                | UFZ - Centre for environmental research |
|                      | `geo_loc_name`    | Geographic location (country and/or region)                   | [MIXS:0000010](https://w3id.org/mixs/0000010)                     | Free text or ontology term      | USA: Maryland, Bethesda                 |
|                      | `lat`             | Latitude in decimal degrees (WGS84)                           | [MIXS:0000009](https://w3id.org/mixs/0000009)                     | Decimal degrees, up to 8 digits | -41.373744                              |
|                      | `lon`             | Longitude in decimal degrees (WGS84)                          | [MIXS:0000009](https://w3id.org/mixs/0000009)                     | Decimal degrees, up to 8 digits | 146.266145                              |
|                      | `elev`            | Elevation from Earth's surface in meters                      | [MIXS:0000093](https://w3id.org/mixs/0000093)                     | Meters                          | 100 m                                   |
|                      | `depth`           | Depth from surface (for soil or sediment samples)             | [MIXS:0000018](https://w3id.org/mixs/0000018)                     | Meters                          | 100 m                                   |

Further metadata fields, including **sample**, **host**, and **environmental** metadata, are also validated according to their respective MIXS terms and ontologies.

---

## Future Work

* Expansion to other MIXS packages (e.g., host-associated, built environment).
* Full ENA submission automation (metadata XML generation, file uploads).
* GUI interface for simplified data upload.

---

## References

* [MIXS Standard - GSC](https://www.nature.com/articles/nbt1366)
* [MIXS Term Browser](https://w3id.org/mixs/)
* [ENA Submission Portal](https://www.ebi.ac.uk/ena/browser/submit)

