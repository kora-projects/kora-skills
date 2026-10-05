# OpenAPI Response Reference — Kora 2.x

Every generated server operation returns a nested type of `<Tag>ApiResponses`. Kora has no
`ResponseEntity` on the server contract, and the delegate never builds an `HttpServerResponse`
itself: it names a status by picking a record, and a generated `HttpServerResponseMapper` turns
that into the wire response.

## Contents

- [1. Two shapes: single-status and sealed](#1-two-shapes-single-status-and-sealed)
- [2. Naming rules](#2-naming-rules)
- [3. Record components](#3-record-components)
- [4. Response headers](#4-response-headers)
- [5. The `default` response and its status code](#5-the-default-response-and-its-status-code)
- [6. Picking a response in the delegate](#6-picking-a-response-in-the-delegate)
- [7. The generated response mappers](#7-the-generated-response-mappers)
- [8. Errors outside the contract](#8-errors-outside-the-contract)
- [9. Status-code ranges (`4XX`, `5XX`)](#9-status-code-ranges-4xx-5xx)
- [10. Common pitfalls](#10-common-pitfalls)

---

## 1. Two shapes: single-status and sealed

**One declared response → one record, no hierarchy.**

```java
public interface PetsApiResponses {
  /** Expected response to a valid request (status code 200) */
  record ShowPetByIdApiResponse(PetCat content) { }
}
```

```kotlin
public interface PetsApiResponses {
  public data class ShowPetByIdApiResponse(public val content: PetCat)
}
```

**Two or more declared responses → a `sealed` interface with one record per status.**

```java
public interface PetsApiResponses {
  sealed interface ListPetsApiResponse {
    /** A paged array of pets (status code 200) */
    record ListPets200ApiResponse(List<Pet> content, String xNext, String xOptionalNext)
        implements ListPetsApiResponse { }

    /** unexpected error (status code 0) */
    record ListPetsDefaultApiResponse(int statusCode, ModelError content)
        implements ListPetsApiResponse { }
  }
}
```

Because the multi-status form is `sealed`, a Java `switch` pattern match or a Kotlin `when` over
it is exhaustive without a default branch — the compiler tells you when a new status is added to
the contract.

## 2. Naming rules

| Element | Name |
|---|---|
| Container | `<Tag as classname>ApiResponses` — e.g. `PetApiResponses` |
| Per-operation type | `<OperationId capitalised>ApiResponse` — e.g. `GetPetByIdApiResponse` |
| Per-status record (multi-status) | `<OperationId capitalised><Code>ApiResponse` — e.g. `GetPetById404ApiResponse` |
| `default` response record | `<OperationId capitalised>DefaultApiResponse` |
| range response record | `<OperationId capitalised>4XXApiResponse`, `…5XXApiResponse` |

Nesting is `PetApiResponses.GetPetByIdApiResponse.GetPetById404ApiResponse`. Kotlin uses
`class` for a status with no data and `data class` otherwise.

## 3. Record components

Components are appended in this order:

1. `int statusCode` — only for the `default` response and for range responses (`4XX`, `5XX`);
2. `content` — only when the response declares a body, typed as the model, `List<Model>`,
   `byte[]` for `format: binary`, or the `rawBodyMode` type for a bare object;
3. one `String` component per declared response header, named from the header in camel case.

A status with no body and no headers is an empty record: `new GetPetById404ApiResponse()`.

## 4. Response headers

Declared response headers become constructor components, and the generated mapper writes them:

```yaml
responses:
  '200':
    description: A paged array of pets
    headers:
      x-next:
        required: true
        schema: { type: string }
      x-optional-next:
        schema: { type: string }
```

```java
record ListPets200ApiResponse(List<Pet> content, String xNext, String xOptionalNext)
    implements ListPetsApiResponse { }
```

```java
// generated mapper
var headers = HttpHeaders.of();
headers.set("x-next", rs.xNext());
if (rs.xOptionalNext() != null) {
  headers.set("x-optional-next", rs.xOptionalNext());
}
```

A header that is not `required` may be passed `null`; a required one may not. There is no way to
add an undeclared header from the delegate — declare it in the contract.

## 5. The `default` response and its status code

An OpenAPI `default` response has no fixed status, so its record takes the status as its first
component:

```java
return new PetsApiResponses.ListPetsApiResponse.ListPetsDefaultApiResponse(
        503, new ModelError(503, "upstream unavailable"));
```

The generated mapper emits `HttpResponseEntity.of(rs.statusCode(), headers, rs.content())`. The
Javadoc on the record says "status code 0" — that is the placeholder the OpenAPI tooling uses
for `default`, not a status Kora will send.

Prefer explicit statuses in the contract. A `default` response is the right tool only for a
genuinely open-ended error channel.

## 6. Picking a response in the delegate

===! ":fontawesome-brands-java: `Java`"

    ```java
    @Override
    public PetApiResponses.GetPetByIdApiResponse getPetById(long petId) {
        if (petId < 0) {
            return new PetApiResponses.GetPetByIdApiResponse.GetPetById400ApiResponse();
        }
        var pet = petService.find(petId);
        return pet == null
            ? new PetApiResponses.GetPetByIdApiResponse.GetPetById404ApiResponse()
            : new PetApiResponses.GetPetByIdApiResponse.GetPetById200ApiResponse(pet);
    }
    ```

    A conditional expression needs the sealed supertype to be inferred; when Java picks the
    record type instead, name it explicitly:

    ```java
    return petService.find(petId)
        .<PetApiResponses.GetPetByIdApiResponse>map(p ->
            new PetApiResponses.GetPetByIdApiResponse.GetPetById200ApiResponse(p))
        .orElseGet(() ->
            new PetApiResponses.GetPetByIdApiResponse.GetPetById404ApiResponse());
    ```

=== ":simple-kotlin: `Kotlin`"

    ```kotlin
    override fun getPetById(petId: Long): PetApiResponses.GetPetByIdApiResponse {
        if (petId < 0) {
            return PetApiResponses.GetPetByIdApiResponse.GetPetById400ApiResponse()
        }
        val pet = petService.find(petId)
            ?: return PetApiResponses.GetPetByIdApiResponse.GetPetById404ApiResponse()
        return PetApiResponses.GetPetByIdApiResponse.GetPetById200ApiResponse(pet)
    }
    ```

Consuming a sealed response (for example in a test or an adapter):

```java
var text = switch (response) {
    case PetApiResponses.GetPetByIdApiResponse.GetPetById200ApiResponse ok -> ok.content().name();
    case PetApiResponses.GetPetByIdApiResponse.GetPetById400ApiResponse bad -> "bad request";
    case PetApiResponses.GetPetByIdApiResponse.GetPetById404ApiResponse nf  -> "not found";
};
```

```kotlin
val text = when (response) {
    is PetApiResponses.GetPetByIdApiResponse.GetPetById200ApiResponse -> response.content.name
    is PetApiResponses.GetPetByIdApiResponse.GetPetById400ApiResponse -> "bad request"
    is PetApiResponses.GetPetByIdApiResponse.GetPetById404ApiResponse -> "not found"
}
```

## 7. The generated response mappers

`<Tag>ApiServerResponseMappers` holds one `HttpServerResponseMapper` per operation, annotated
`@Component @DefaultComponent`, and the controller method is wired to it with
`@Mapping(<Tag>ApiServerResponseMappers.<Op>ApiResponseMapper.class)`:

```java
@Component
@DefaultComponent
class ListPetsApiResponseMapper implements HttpServerResponseMapper<PetsApiResponses.ListPetsApiResponse> {

  ListPetsApiResponseMapper(
      @Json HttpServerResponseMapper<HttpResponseEntity<List<Pet>>> response200Delegate,
      @Json HttpServerResponseMapper<HttpResponseEntity<ModelError>> response0Delegate) { … }

  @Override
  public HttpServerResponse apply(HttpServerRequest request, PetsApiResponses.ListPetsApiResponse response) {
    switch (response) {
      case …ListPets200ApiResponse rs -> {
        var headers = HttpHeaders.of();
        headers.set("x-next", rs.xNext());
        var entity = HttpResponseEntity.of(200, headers, rs.content());
        return this.response200Delegate.apply(request, entity);
      }
      …
    }
  }
}
```

Two consequences:

- **JSON serialisation is delegated**, so `JsonModule` must be in the `@KoraApp` graph; the body
  writers come from the `@Json`-tagged `HttpServerResponseMapper` for each payload type.
- Because the mapper is `@DefaultComponent`, you may override the whole per-operation mapping by
  declaring your own `@Component` `HttpServerResponseMapper` for the same response type. That is
  the supported escape hatch for a response the contract cannot describe — not editing generated
  code.

A status with neither body nor headers short-circuits to `HttpServerResponse.of(201, headers)`,
so `204`/`201`-style empty responses cost nothing.

## 8. Errors outside the contract

Throwing `io.koraframework.http.server.common.response.HttpServerResponseException` from the
delegate bypasses the response mapper entirely:

```java
throw HttpServerResponseException.of(409, "pet already exists");
```

Use it for conditions the contract does not model; prefer a declared status record when it does.
Validation failures are turned into a response by `ValidationHttpServerInterceptor` — see
[Validation Reference](openapi-validation-reference.md). Authentication failures produce
`401` (and a principal without a required OAuth2 scope `403`) inside the generated `ApiSecurity`
interceptor — see
[Authorization Reference](authorization-reference.md).

## 9. Status-code ranges (`4XX`, `5XX`)

OpenAPI lets a response cover a whole class of statuses (`1XX` … `5XX`). A range is not a single
code, so its record takes the real status as its first component, exactly like `default`:

```yaml
responses:
  '200': { description: OK, content: { application/json: { schema: { $ref: '#/components/schemas/Pet' } } } }
  '4XX': { description: Client error, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
  '5XX': { description: Server error, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
```

```java
record ListPets4XXApiResponse(int statusCode, ModelError content) implements ListPetsApiResponse { }
record ListPets5XXApiResponse(int statusCode, ModelError content) implements ListPetsApiResponse { }
```

```java
return new PetsApiResponses.ListPetsApiResponse.ListPets4XXApiResponse(
        409, new ModelError(409, "pet already exists"));
```

The generated mapper writes `HttpResponseEntity.of(rs.statusCode(), …)`, so the status you pass is
the status sent. Nothing checks that it lies inside the range — pass a 4xx code to the `4XX`
record. Exact codes declared next to a range keep their own record.

## 10. Common pitfalls

| Symptom | Cause and fix |
|---|---|
| No record for the status you want | Only declared statuses are generated. Add `"500": { description: … }` to that operation and regenerate. |
| `incompatible types: GetPetById200ApiResponse cannot be converted to …` | The ternary/lambda inferred the record type. Annotate the target type or split into `if`/`return`. |
| `the switch statement does not cover all possible input values` | A status was added to the contract; handle the new record. |
| Header missing from the wire response | The header is not declared under that response in the contract, so the mapper never writes it. |
| `default` response returns `0` | You passed `0` as `statusCode`; the record's first component is the real status. |
| `4XX` record sent with a 5xx status | The range record sends whatever `statusCode` you pass; nothing validates it against the range. |
| Wrong `Content-Type` on a `byte[]` body | Declare the media type on that response; binary responses carry their content type from the contract. |
| Returned a raw DTO | Return the generated record; there is no `ResponseEntity` in Kora. |

## Related

- [Delegates Reference](openapi-delegates-reference.md)
- [Controllers Reference](openapi-controllers-reference.md)
- [Models Reference](openapi-models-reference.md)
- [Codegen Reference](openapi-codegen-reference.md)
