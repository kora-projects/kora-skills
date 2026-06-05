# Contract Analysis

Generated from `spec-openapi.yaml` for PetClinic API v1.0

## Endpoints (N=10)

| Method | Path | Operation | Request Schema | Response Schema | Status Codes |
|--------|------|-----------|----------------|-----------------|--------------|
| POST | /owner | addOwner | OwnerFields | Owner | 201, 400, 500 |
| GET | /owner | listOwners | - | Array<Owner> | 200, 304, 500 |
| GET | /owner/{ownerId} | getOwner | - | Owner | 200, 304, 400, 404, 500 |
| PUT | /owner/{ownerId} | updateOwner | OwnerFields | Owner | 200, 400, 404, 500 |
| POST | /owner/{ownerId}/pet | addPet | PetFields | - | 201, 400, 404, 500 |
| GET | /owner/{ownerId}/pet/{petId} | getPet | - | Pet | 200, 304, 400, 404, 500 |
| PUT | /owner/{ownerId}/pet/{petId} | updatePet | PetFields | - | 204, 400, 404, 500 |
| POST | /owner/{ownerId}/pet/{petId}/visit | addVisit | VisitFields | - | 201, 400, 404, 500 |
| GET | /pet-type | listPetTypes | - | Array<PetType> | 200, 304, 500 |
| GET | /vet | listVets | - | Array<Vet> | 200, 304, 500 |

## Domain Models (N=8)

### OwnerFields
| Property | Type | Constraints |
|----------|------|-------------|
| firstName | string | minLength: 1, maxLength: 30, pattern: ^[a-zA-Z]*$ |
| lastName | string | minLength: 1, maxLength: 30, pattern: ^[a-zA-Z]*$ |
| address | string | minLength: 1, maxLength: 255 |
| city | string | minLength: 1, maxLength: 80 |
| telephone | string | minLength: 1, maxLength: 20, pattern: ^[0-9]*$ |

### Owner
| Property | Type | Constraints |
|----------|------|-------------|
| id | integer (int32) | readOnly, minimum: 0 |
| firstName | string | minLength: 1, maxLength: 30, pattern: ^[a-zA-Z]*$ |
| lastName | string | minLength: 1, maxLength: 30, pattern: ^[a-zA-Z]*$ |
| address | string | minLength: 1, maxLength: 255 |
| city | string | minLength: 1, maxLength: 80 |
| telephone | string | minLength: 1, maxLength: 20, pattern: ^[0-9]*$ |
| pets | Array<Pet> | readOnly |

### PetFields
| Property | Type | Constraints |
|----------|------|-------------|
| name | string | maxLength: 30 |
| birthDate | string (date) | - |
| typeId | integer (int32) | - |

### Pet
| Property | Type | Constraints |
|----------|------|-------------|
| id | integer (int32) | readOnly, minimum: 0 |
| name | string | maxLength: 30 |
| birthDate | string (date) | - |
| typeId | integer (int32) | - |
| type | PetType | readOnly |
| visits | Array<Visit> | readOnly |

### PetType
| Property | Type | Constraints |
|----------|------|-------------|
| id | integer (int32) | readOnly, minimum: 0 |
| name | string | maxLength: 80 |

### Vet
| Property | Type | Constraints |
|----------|------|-------------|
| id | integer (int32) | readOnly, minimum: 0 |
| firstName | string | minLength: 1, maxLength: 30, pattern: ^[a-zA-Z]*$ |
| lastName | string | minLength: 1, maxLength: 30, pattern: ^[a-zA-Z]*$ |
| specialties | Array<Specialty> | - |

### Specialty
| Property | Type | Constraints |
|----------|------|-------------|
| id | integer (int32) | readOnly, minimum: 0 |
| name | string | maxLength: 80 |

### VisitFields
| Property | Type | Constraints |
|----------|------|-------------|
| date | string (date) | - |
| description | string | minLength: 1, maxLength: 255 |

### Visit
| Property | Type | Constraints |
|----------|------|-------------|
| id | integer (int32) | readOnly, minimum: 0 |
| date | string (date) | - |
| description | string | minLength: 1, maxLength: 255 |

### RestError
| Property | Type | Constraints |
|----------|------|-------------|
| status | integer (int32) | readOnly |
| error | string | readOnly |
| path | string (uri) | readOnly |
| timestamp | string (date-time) | readOnly |
| message | string | readOnly |
| schemaValidationErrors | Array<ValidationMessage> | - |
| trace | string | readOnly |

## Relationships

```
Owner (1) ----< (N) Pet
Pet (1) ----< (N) Visit
Pet (N) >---- (1) PetType
Vet (N) >---- (N) Specialty (via vet_specialties join table)
```

## Implementation Order

1. **PetType** — no dependencies (lookup table)
2. **Specialty** — no dependencies (lookup table)
3. **Vet** — depends on Specialty (many-to-many)
4. **Owner** — no dependencies
5. **Pet** — depends on Owner (owner_id FK), PetType (type_id FK)
6. **Visit** — depends on Pet (pet_id FK)

## Validation Rules Summary

### Owner
- firstName: required, 1-30 chars, letters only
- lastName: required, 1-30 chars, letters only
- address: required, 1-255 chars
- city: required, 1-80 chars
- telephone: required, 1-20 chars, digits only

### Pet
- name: optional, max 30 chars
- birthDate: optional, date format (YYYY-MM-DD)
- typeId: optional, integer

### Vet
- firstName: required, 1-30 chars, letters only
- lastName: required, 1-30 chars, letters only
- specialties: required, array of Specialty

### Specialty
- id: required, integer (read-only)
- name: required, max 80 chars

### PetType
- id: required, integer (read-only)
- name: required, max 80 chars

### Visit
- date: optional, date format (YYYY-MM-DD)
- description: required, 1-255 chars

## Error Response Schema

All error responses follow the `RestError` schema with:
- HTTP status code
- Short error message
- Request path
- Timestamp
- Long error message
- Schema validation errors (array)
- Stack trace (for debugging)

## ETag Support

The following endpoints support ETag headers for conditional requests:
- GET /owner
- GET /owner/{ownerId}
- GET /owner/{ownerId}/pet/{petId}
- GET /pet-type
- GET /vet

Returns `304 Not Modified` when ETag matches.
