# Custom JSON Readers and Writers

**Source:** [.kora-agent/kora-docs/mkdocs/docs/en/documentation/json.md](.kora-agent/kora-docs/mkdocs/docs/en/documentation/json.md)  
**Examples:** `.kora-agent/kora-examples/kora-java-json-module/`

## 1. Overview

Kora JSON module allows creating custom `JsonReader` and `JsonWriter` for: **Custom types** | **Special formatting** | **Legacy compatibility** | **Performance optimization**.

## 2. JsonReader Interface

**Interface:**
```java
public interface JsonReader<T> { T read(JsonParser parser) throws IOException; }
```

**Example: Custom Reader**
```java
public class UserIdReader implements JsonReader<UserId> {
    @Override public UserId read(JsonParser parser) throws IOException {
        String value = parser.nextString();
        return UserId.from(value);  // Custom parsing
    }
}
```

**Registering in Module:**
```java
@Module
public interface CustomJsonModule {
    @DefaultComponent default JsonReader<UserId> userIdReader() { return new UserIdReader(); }
}
@KoraApp
public interface Application extends JsonModule, CustomJsonModule {
    static void main(String[] args) { KoraApplication.run(ApplicationGraph::graph); }
}
```

## 3. JsonWriter Interface

**Interface:**
```java
public interface JsonWriter<T> { void write(JsonGenerator generator, T value) throws IOException; }
```

**Example: Custom Writer**
```java
public class UserIdWriter implements JsonWriter<UserId> {
    @Override public void write(JsonGenerator generator, UserId value) throws IOException {
        generator.writeString(value != null ? value.toString() : null);
    }
}
```

**Registering in Module:**
```java
@Module
public interface CustomJsonModule {
    @DefaultComponent default JsonWriter<UserId> userIdWriter() { return new UserIdWriter(); }
}
```

---

## 4. Combined Reader + Writer

**Combined Mapper:**
```java
public class UserIdMapper implements JsonReader<UserId>, JsonWriter<UserId> {
    @Override public UserId read(JsonParser parser) throws IOException {
        String value = parser.nextString(); return UserId.from(value);
    }
    @Override public void write(JsonGenerator generator, UserId value) throws IOException {
        generator.writeString(value != null ? value.toString() : null);
    }
}
```

**Registering:**
```java
@Module
public interface CustomJsonModule {
    @DefaultComponent default UserIdMapper userIdMapper() { return new UserIdMapper(); }
}
```

## 5. Common Use Cases

### 5.1 Date/Time with Custom Format

```java
@Module
public interface DateTimeModule {
     
    @DefaultComponent
    default JsonReader<LocalDate> localDateReader() { 
        DateTimeFormatter formatter = DateTimeFormatter.ofPattern("dd.MM.yyyy");
        return parser -> { 
            String value = parser.nextString();
            return LocalDate.parse(value, formatter); 
        };
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
{
    "birthDate": "15.01.1990"
}
```

### 5.2 Enum with Custom Mapping

```java
public enum Status {
    ACTIVE("A"), 
    INACTIVE("I"),
    PENDING("P"); 
    
    private final String code; 
    
    Status(String code) { 
        this.code = code;
    } 
    
    public static Status fromCode(String code) { 
        return Arrays.stream(values())
            .filter(s -> s.code.equals(code)) 
            .findFirst()
            .orElseThrow(() -> new IllegalArgumentException("Unknown status: " + code)); 
    }
}
```

**Custom mapper:**

```java
@Module
public interface StatusModule {
     
    @DefaultComponent
    default JsonReader<Status> statusReader() { 
        return parser -> {
            String code = parser.nextString(); 
            return Status.fromCode(code);
        }; 
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
{
    "status": "A"  // Instead of "ACTIVE"
}
```

### 5.3 Money/Currency

```java
public class MoneyReader implements JsonReader<Money> {
     
    @Override
    public Money read(JsonParser parser) throws IOException { 
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
{
    "price": { 
        "amount": 99.99,
        "currency": "USD" 
    }
}
```

### 5.4 Base64 Encoding

```java
@Module
public interface BinaryModule {
     
    @DefaultComponent
    default JsonReader<byte[]> base64ByteArrayReader() { 
        return parser -> {
            String base64 = parser.nextString(); 
            return Base64.getDecoder().decode(base64);
        }; 
    }
     
    @DefaultComponent
    default JsonWriter<byte[]> base64ByteArrayWriter() { 
        return (generator, value) -> {
            if (value != null) { 
                String base64 = Base64.getEncoder().encodeToString(value);
                generator.writeString(base64); 
            } else {
                generator.writeNull(); 
            }
        }; 
    }
}
```

**JSON format:**

```json
{
    "signature": "SGVsbG8gV29ybGQ="
}
```

---

## 6. Conditional Readers/Writers

### 6.1 Using Config for Format Selection

```java
@Module
public interface ConfigurableDateModule {
     
    @DefaultComponent
    default JsonReader<LocalDate> localDateReader(Config config) { 
        String format = config.getString("date.format", "yyyy-MM-dd");
        DateTimeFormatter formatter = DateTimeFormatter.ofPattern(format); 
        
        return parser -> { 
            String value = parser.nextString();
            return LocalDate.parse(value, formatter); 
        };
    }
}
```

**Configuration:**

```hocon
date {
    format = "dd.MM.yyyy"
}
```

### 6.2 Environment-Specific Formatting

```java
@Module
public interface EnvironmentModule {
     
    @DefaultComponent
    default JsonWriter<Instant> instantWriter(Config config) { 
        String env = config.getString("app.environment", "production");
         
        if ("development".equals(env)) {
            // Human-readable format for dev 
            return (generator, value) -> {
                generator.writeString(value.toString());  // ISO-8601 
            };
        } else { 
            // Unix timestamp for production (smaller payload)
            return (generator, value) -> { 
                generator.writeNumber(value.toEpochMilli());
            }; 
        }
    }
}
```

---

## 7. Integration with @Json DTOs

### 7.1 Using Custom Reader in DTO

```java
@Json
public record OrderRequest(
    String orderId, 
    @JsonField("customer_id")
    CustomerId customerId,  // Custom type with custom reader 
    List<OrderItem> items
) {}
```

**Custom reader:**

```java
@Module
public interface CustomerModule {
     
    @DefaultComponent
    default JsonReader<CustomerId> customerIdReader() { 
        return parser -> {
            String value = parser.nextString(); 
            return CustomerId.from(value);
        }; 
    }
}
```

### 7.2 Using Custom Writer in DTO

```java
@Json
public record OrderResponse(
    String orderId, 
    CustomerId customerId,
    Money totalAmount,  // Custom type with custom writer 
    LocalDateTime createdAt
) {}
```

**Custom writer:**

```java
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

### 8.1 Unit Test for Reader

```java
class UserIdReaderTest {
     
    private final JsonReader<UserId> reader = new UserIdReader();
     
    @Test
    void testReadValidId() throws IOException { 
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

### 8.2 Unit Test for Writer

```java
class UserIdWriterTest {
     
    private final JsonWriter<UserId> writer = new UserIdWriter();
     
    @Test
    void testWriteValidId() throws IOException { 
        StringWriter stringWriter = new StringWriter();
        JsonFactory factory = new JsonFactory(); 
        
        try (JsonGenerator generator = factory.createGenerator(stringWriter)) { 
            UserId userId = UserId.from("usr_123456");
            writer.write(generator, userId); 
        }
         
        assertThat(stringWriter.toString()).isEqualTo("\"usr_123456\"");
    } 
    
    @Test 
    void testWriteNull() throws IOException {
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

### 9.1 Error Handling

```java
public class SafeUserIdReader implements JsonReader<UserId> {
     
    @Override
    public UserId read(JsonParser parser) throws IOException { 
        try {
            String value = parser.nextString(); 
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

### 9.2 Null Handling

Always handle null values explicitly:

```java
// GOOD
@Override
public void write(JsonGenerator generator, UserId value) throws IOException {
    if (value != null) { 
        generator.writeString(value.toString());
    } else { 
        generator.writeNull();
    }
}

// BAD — NPE if value is null
@Override
public void write(JsonGenerator generator, UserId value) throws IOException {
    generator.writeString(value.toString());  // NPE!
}
```

### 9.3 Performance Considerations

**Cache formatters:**

```java
// GOOD — cache formatter
public class CachedDateWriter implements JsonWriter<LocalDate> {
    private static final DateTimeFormatter FORMATTER =  
        DateTimeFormatter.ofPattern("dd.MM.yyyy");
     
    @Override
    public void write(JsonGenerator generator, LocalDate value) throws IOException { 
        if (value != null) {
            generator.writeString(value.format(FORMATTER)); 
        } else {
            generator.writeNull(); 
        }
    }
}

// BAD — create formatter every time
public class SlowDateWriter implements JsonWriter<LocalDate> {
    @Override 
    public void write(JsonGenerator generator, LocalDate value) throws IOException {
        generator.writeString( 
            value.format(DateTimeFormatter.ofPattern("dd.MM.yyyy"))  // Created every call!
        ); 
    }
}
```

---

## 10. Quick Reference

### Reader Template

```java
public class CustomReader implements JsonReader<CustomType> {
     
    @Override
    public CustomType read(JsonParser parser) throws IOException { 
        String value = parser.nextString();
        return CustomType.from(value); 
    }
}
```

### Writer Template

```java
public class CustomWriter implements JsonWriter<CustomType> {
     
    @Override
    public void write(JsonGenerator generator, CustomType value) throws IOException { 
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
