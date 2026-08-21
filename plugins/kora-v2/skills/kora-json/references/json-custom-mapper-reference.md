# Custom JSON Mappers Reference

Source of truth: `.kora-agent/kora-docs/mkdocs/docs/en/documentation/json.md`
(section "Custom types").

## Contents

1. [Overview](#1-overview)
2. [JsonReader interface](#2-jsonreader-interface)
3. [JsonWriter interface](#3-jsonwriter-interface)
4. [Combined reader + writer](#4-combined-reader--writer)
5. [Common use cases](#5-common-use-cases)
6. [Config-driven readers/writers](#6-config-driven-readerswriters)
7. [Integration with @Json DTOs](#7-integration-with-json-dtos)
8. [Testing custom mappers](#8-testing-custom-mappers)
9. [Best practices](#9-best-practices)
10. [Quick reference](#10-quick-reference)

---

## 1. Overview

When a type is not in the built-in supported list, register a factory that provides a
`JsonReader<T>` and/or `JsonWriter<T>`. Use cases:

- Custom value types (e.g. `UserId`, `Money`)
- A non-standard wire format for a built-in type (e.g. a custom date pattern)
- Compatibility with a legacy JSON layout

Two equivalent ways to register the factory:

- a `default` method directly in the `@KoraApp` interface (overrides the default binding), or
- a `@DefaultComponent` factory method inside a `@Module` the app extends (a low-priority
  binding that any non-default factory can override).

Both make the mapper available to every `@Json` DTO that contains the custom type.

---

## 2. JsonReader Interface

**Interface:**
```java
public interface JsonReader<T> { 
    T read(JsonParser parser); 
}
```

**Example: Custom Reader**
```java
public class UserIdReader implements JsonReader<UserId> {
    @Override 
    public UserId read(JsonParser parser) {
        String value = parser.getText();
        return UserId.from(value);  // Custom parsing
    }
}
```

**Registering in Module:**
```java
@Module
public interface CustomJsonModule {
    @DefaultComponent 
    default JsonReader<UserId> userIdReader() { 
        return new UserIdReader(); 
    }
}

@KoraApp
public interface Application extends JsonModule, CustomJsonModule {
    static void main(String[] args) { 
        KoraApplication.run(ApplicationGraph::graph); 
    }
}
```

---

## 3. JsonWriter Interface

**Interface:**
```java
public interface JsonWriter<T> { 
    void write(JsonGenerator generator, T value); 
}
```

**Example: Custom Writer**
```java
public class UserIdWriter implements JsonWriter<UserId> {
    @Override 
    public void write(JsonGenerator generator, UserId value) {
        generator.writeString(value != null ? value.toString() : null);
    }
}
```

**Registering in Module:**
```java
@Module
public interface CustomJsonModule {
    @DefaultComponent 
    default JsonWriter<UserId> userIdWriter() { 
        return new UserIdWriter(); 
    }
}
```

---

## 4. Combined Reader + Writer

**Combined Mapper:**
```java
public class UserIdMapper implements JsonReader<UserId>, JsonWriter<UserId> {
    @Override 
    public UserId read(JsonParser parser) {
        String value = parser.getText(); 
        return UserId.from(value);
    }
    
    @Override 
    public void write(JsonGenerator generator, UserId value) {
        generator.writeString(value != null ? value.toString() : null);
    }
}
```

**Registering:**
```java
@Module
public interface CustomJsonModule {
    @DefaultComponent 
    default UserIdMapper userIdMapper() { 
        return new UserIdMapper(); 
    }
}
```

---

## 5. Common Use Cases

### Date/Time with Custom Format

```java
@Module
public interface DateTimeModule {
     
    @DefaultComponent
    default JsonReader<LocalDate> localDateReader() { 
        DateTimeFormatter formatter = DateTimeFormatter.ofPattern("dd.MM.yyyy");
        return parser -> LocalDate.parse(parser.getText(), formatter);
    } 
    
    @DefaultComponent 
    default JsonWriter<LocalDate> localDateWriter() {
        DateTimeFormatter formatter = DateTimeFormatter.ofPattern("dd.MM.yyyy"); 
        return (generator, value) -> {
            if (value != null) { 
                generator.writeString(value.format(formatter));
            } else { 
                generator.writeNull();
            } 
        };
    }
}
```

**JSON format:**
```json
{ "birthDate": "15.01.1990" }
```

### Enum with Custom Mapping

```java
public enum Status {
    ACTIVE("A"), INACTIVE("I"), PENDING("P"); 
    
    private final String code; 
    
    Status(String code) { this.code = code; } 
    
    public static Status fromCode(String code) { 
        return Arrays.stream(values())
            .filter(s -> s.code.equals(code)) 
            .findFirst()
            .orElseThrow(() -> new IllegalArgumentException("Unknown: " + code)); 
    }
}

@Module
public interface StatusModule {
    @DefaultComponent
    default JsonReader<Status> statusReader() { 
        return parser -> Status.fromCode(parser.getText());
    }
    
    @DefaultComponent
    default JsonWriter<Status> statusWriter() { 
        return (generator, value) -> {
            if (value != null) { 
                generator.writeString(value.code);
            } else { 
                generator.writeNull();
            } 
        };
    }
}
```

**JSON format:**
```json
{ "status": "A" }  // Instead of "ACTIVE"
```

### Money/Currency

```java
public class MoneyReader implements JsonReader<Money> {
    @Override
    public Money read(JsonParser parser) { 
        parser.nextToken();  // Start object
        BigDecimal amount = null; 
        String currency = null;
         
        while (parser.nextToken() != JsonToken.END_OBJECT) {
            String fieldName = parser.currentName(); 
            parser.nextToken();
             
            if ("amount".equals(fieldName)) {
                amount = parser.getDecimalValue(); 
            } else if ("currency".equals(fieldName)) {
                currency = parser.getText(); 
            }
        } 
        
        return new Money(amount, Currency.getInstance(currency)); 
    }
}
```

**JSON format:**
```json
{ "price": { "amount": 99.99, "currency": "USD" } }
```

### Base64 Encoding

```java
@Module
public interface BinaryModule {
     
    @DefaultComponent
    default JsonReader<byte[]> base64ByteArrayReader() { 
        return parser -> Base64.getDecoder().decode(parser.getText());
    }
     
    @DefaultComponent
    default JsonWriter<byte[]> base64ByteArrayWriter() { 
        return (generator, value) -> {
            if (value != null) { 
                generator.writeString(Base64.getEncoder().encodeToString(value));
            } else {
                generator.writeNull(); 
            }
        }; 
    }
}
```

**JSON format:**
```json
{ "signature": "SGVsbG8gV29ybGQ=" }
```

---

## 6. Config-driven Readers/Writers

Drive the format from a typed `@ConfigSource` (Kora's `Config` has no
`getString(key, default)` — use a config interface instead). Inject it into the factory:

```java
@ConfigSource("json.date")
public interface DateFormatConfig {
    default String pattern() { return "yyyy-MM-dd"; } // overridable via HOCON
}

@Module
public interface ConfigurableDateModule {

    @DefaultComponent
    default JsonReader<LocalDate> localDateReader(DateFormatConfig config) {
        var formatter = DateTimeFormatter.ofPattern(config.pattern());
        return parser -> LocalDate.parse(parser.getText(), formatter);
    }

    @DefaultComponent
    default JsonWriter<LocalDate> localDateWriter(DateFormatConfig config) {
        var formatter = DateTimeFormatter.ofPattern(config.pattern());
        return (generator, value) -> {
            if (value != null) {
                generator.writeString(value.format(formatter));
            } else {
                generator.writeNull();
            }
        };
    }
}
```

**Configuration (HOCON):**
```hocon
json {
    date {
        pattern = "dd.MM.yyyy"
    }
}
```

---

## 7. Integration with @Json DTOs

### Using Custom Reader in DTO

```java
@Json
public record OrderRequest(
    String orderId, 
    @JsonField("customer_id") CustomerId customerId,  // Custom type
    List<OrderItem> items
) {}

@Module
public interface CustomerModule {
    @DefaultComponent
    default JsonReader<CustomerId> customerIdReader() { 
        return parser -> CustomerId.from(parser.getText());
    }
}
```

### Using Custom Writer in DTO

```java
@Json
public record OrderResponse(
    String orderId, 
    CustomerId customerId,
    Money totalAmount,  // Custom type
    LocalDateTime createdAt
) {}

@Module
public interface MoneyModule {
    @DefaultComponent
    default JsonWriter<Money> moneyWriter() { 
        return (generator, value) -> {
            generator.writeStartObject(); 
            generator.writeNumberField("amount", value.getAmount());
            generator.writeStringField("currency", value.getCurrency().getCode()); 
            generator.writeEndObject();
        }; 
    }
}
```

---

## 8. Testing Custom Mappers

### Unit Test for Reader

```java
class UserIdReaderTest {
    private final JsonReader<UserId> reader = new UserIdReader();
    
    @Test
    void testReadValidId() { 
        JsonFactory factory = new JsonFactory();
        try (JsonParser parser = factory.createParser("\"usr_123456\"")) { 
            UserId userId = reader.read(parser);
            assertThat(userId.value()).isEqualTo("usr_123456"); 
        }
    } 
    
    @Test 
    void testReadInvalidId() {
        JsonFactory factory = new JsonFactory(); 
        try (JsonParser parser = factory.createParser("\"invalid\"")) {
            assertThatThrownBy(() -> reader.read(parser)) 
                .isInstanceOf(IllegalArgumentException.class);
        } 
    }
}
```

### Unit Test for Writer

```java
class UserIdWriterTest {
    private final JsonWriter<UserId> writer = new UserIdWriter();
    
    @Test
    void testWriteValidId() { 
        StringWriter stringWriter = new StringWriter();
        JsonFactory factory = new JsonFactory(); 
        
        try (JsonGenerator generator = factory.createGenerator(stringWriter)) { 
            UserId userId = UserId.from("usr_123456");
            writer.write(generator, userId); 
        }
        
        assertThat(stringWriter.toString()).isEqualTo("\"usr_123456\"");
    } 
    
    @Test 
    void testWriteNull() {
        StringWriter stringWriter = new StringWriter(); 
        JsonFactory factory = new JsonFactory();
        
        try (JsonGenerator generator = factory.createGenerator(stringWriter)) {
            writer.write(generator, null); 
        }
        
        assertThat(stringWriter.toString()).isEqualTo("null");
    }
}
```

---

## 9. Best Practices

### Error Handling

```java
public class SafeUserIdReader implements JsonReader<UserId> {
    @Override
    public UserId read(JsonParser parser) { 
        try {
            String value = parser.getText(); 
            return UserId.from(value);
        } catch (IllegalArgumentException e) { 
            throw new JsonParseException(
                parser,  
                "Invalid user ID format: " + parser.getText(), 
                e 
            );
        } 
    }
}
```

### Null Handling

Always handle null values explicitly:

```java
// GOOD
@Override
public void write(JsonGenerator generator, UserId value) {
    if (value != null) { 
        generator.writeString(value.toString());
    } else { 
        generator.writeNull();
    }
}

// BAD — NPE if value is null
@Override
public void write(JsonGenerator generator, UserId value) {
    generator.writeString(value.toString());  // NPE!
}
```

### Performance Considerations

**Cache formatters:**

```java
// GOOD — cache formatter
public class CachedDateWriter implements JsonWriter<LocalDate> {
    private static final DateTimeFormatter FORMATTER =  
        DateTimeFormatter.ofPattern("dd.MM.yyyy");
    
    @Override
    public void write(JsonGenerator generator, LocalDate value) { 
        if (value != null) {
            generator.writeString(value.format(FORMATTER)); 
        } else {
            generator.writeNull(); 
        }
    }
}
```

---

## 10. Quick Reference

### Reader Template

```java
public class CustomReader implements JsonReader<CustomType> {
    @Override
    public CustomType read(JsonParser parser) { 
        String value = parser.getText();
        return CustomType.from(value); 
    }
}
```

### Writer Template

```java
public class CustomWriter implements JsonWriter<CustomType> {
    @Override
    public void write(JsonGenerator generator, CustomType value) { 
        if (value != null) {
            generator.writeString(value.toString()); 
        } else {
            generator.writeNull(); 
        }
    }
}
```

### Module Registration

```java
@Module
public interface CustomJsonModule {
    @DefaultComponent
    default JsonReader<CustomType> customTypeReader() { 
        return new CustomReader();
    } 
    
    @DefaultComponent 
    default JsonWriter<CustomType> customTypeWriter() {
        return new CustomWriter(); 
    }
}
```
