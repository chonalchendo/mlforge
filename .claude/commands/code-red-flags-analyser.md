# Ousterhout's 14 Code Red Flags
*From "A Philosophy of Software Design" — Code Review Reference*

---

## Agent Workflow

When scanning code for red flags, follow this workflow:

### Step 1: Discover and Index the Codebase
```
1. List all modules/packages in the target directory (e.g., src/mlforge/)
2. Build a dependency graph (who imports whom)
3. Identify public interfaces vs internal implementation
4. Create a file index with LOC counts for prioritisation
```

### Step 2: Scan for Shallow Modules (Red Flag 1)
```
For each class and module:
- Count public methods/attributes (interface surface)
- Measure implementation size (LOC, complexity)
- Flag where interface size ≈ implementation size
- Look for classes that are mostly getters/setters
- Identify "wrapper" classes that add little value
```

### Step 3: Detect Information Leakage (Red Flag 2)
```
Search for duplicated knowledge:
- Grep for magic strings/numbers appearing in multiple files
- Look for the same data format/structure defined multiple times
- Check if schema/protocol knowledge is centralised or scattered
- Identify "shotgun surgery" patterns (one change → many files)
```

### Step 4: Identify Temporal Decomposition (Red Flag 3)
```
Look for workflow-based organisation:
- Methods named step1, step2, phase_*, *_then_*, *_before_*, *_after_*
- Classes organised by execution order rather than data/responsibility
- Functions that must be called in a specific sequence
- State passed between methods via instance variables
```

### Step 5: Check for Overexposure (Red Flag 4)
```
Examine function/method signatures:
- Functions with >5 parameters (especially optional ones)
- Required knowledge of rarely-used features for common operations
- Configuration objects that expose too many internals
- APIs where simple cases require complex setup
```

### Step 6: Find Pass-Through Methods (Red Flag 5)
```
Scan for delegation patterns:
- Methods whose body is essentially `return self.x.same_method(same_args)`
- Layers that don't transform data or add logic
- Wrapper classes that just forward all calls
- Inheritance used only to delegate
```

### Step 7: Detect Repetition (Red Flag 6)
```
Search for code duplication:
- Near-identical code blocks (use fuzzy matching)
- Similar try/except patterns repeated
- Common setup/teardown code not extracted
- Copy-paste patterns with minor variations
```

### Step 8: Spot Special-General Mixture (Red Flag 7)
```
Look for special cases in general code:
- if statements checking for specific entities/clients/types in generic modules
- Hard-coded special cases in utility functions
- General-purpose classes with client-specific methods
- Configuration that embeds business logic
```

### Step 9: Identify Conjoined Methods (Red Flag 8)
```
Analyse method dependencies:
- Methods that share instance state extensively
- Functions where understanding one requires reading another
- Circular call patterns between methods
- Shared mutable state between "paired" methods
```

### Step 10: Evaluate Comments (Red Flags 9, 10)
```
Audit comment quality:
- Comments that restate the code (e.g., "# increment counter" before `count += 1`)
- Interface docs that mention implementation details
- Missing comments on non-obvious logic
- Stale comments that don't match code
```

### Step 11: Assess Naming (Red Flags 11, 12)
```
Review naming quality:
- Generic names: data, info, temp, result, item, value, manager, handler, process
- Names that required compromise (too long, compound phrases)
- Inconsistent naming conventions
- Names that don't match what the code does
```

### Step 12: Check Documentation Burden (Red Flag 13)
```
Identify documentation complexity:
- Docstrings requiring multiple paragraphs for a single function
- "It depends" or conditional documentation
- Methods needing extensive examples to explain
- Documentation longer than implementation
```

### Step 13: Find Non-Obvious Code (Red Flag 14)
```
Scan for obscure patterns:
- Clever one-liners that require mental parsing
- Hidden side effects in getters or "pure" functions
- Implicit dependencies and magic behaviour
- Code requiring execution tracing to understand
```

### Step 14: Generate Report
```
Structure the output as:

## Summary
[2-3 sentences on overall code health and red flag density]

## Critical Red Flags
[Most severe issues requiring immediate attention, with file:line references]

## Warning Red Flags
[Moderate issues to address in next refactor cycle]

## Minor Red Flags
[Low-priority improvements for future consideration]

## Red Flag Frequency
[Table showing count of each red flag type found]

## Root Cause Analysis
[Common underlying issues causing multiple red flags]

## Recommended Fixes
[Top 5 actionable refactoring suggestions, ordered by impact]
```

### Severity Classification
- **Critical**: Information leakage, conjoined methods, non-obvious code in core paths
- **Warning**: Shallow modules, pass-through methods, repetition
- **Minor**: Comment issues, vague names (isolated cases), slight overexposure

### Analysis Parameters
- **Target directory**: Specified by user (e.g., `src/mlforge/`)
- **Depth**: Analyse all `.py` files recursively
- **Threshold for reporting**: Flag when pattern appears 2+ times or in critical paths
- **Output format**: Markdown report with file:line references

---

## The 14 Red Flags

---

## 1. Shallow Module

**What:** The interface is nearly as complex as the implementation.

**Why:** Shallow modules don't hide complexity—they just move it around.

**Smell:** Class/method has many parameters or methods but each does little work.

```python
# 🚩 RED FLAG: Interface mirrors implementation
class ShallowConfig:
    def load_file(self, path): ...
    def parse_yaml(self, content): ...
    def validate_schema(self, data): ...
    def merge_defaults(self, data, defaults): ...
    def resolve_env_vars(self, data): ...
    # Caller must orchestrate all these steps

# ✅ FIXED: Deep module hides the steps
class Config:
    def load(self, path: str) -> dict:
        """Load, parse, validate, merge defaults, resolve env vars—all handled."""
        pass
```

---

## 2. Information Leakage

**What:** The same design decision appears in multiple modules.

**Why:** Changes require coordinated edits across modules—a maintenance nightmare.

**Smell:** Changing one thing requires changing many files in the same way.

```python
# 🚩 RED FLAG: Wire format knowledge leaked everywhere
class OrderService:
    def save(self, order):
        data = {"id": order.id, "ts": order.timestamp.isoformat()}  # Format here
        self.db.write(data)

class OrderExporter:
    def export(self, order):
        data = {"id": order.id, "ts": order.timestamp.isoformat()}  # Same format!
        return json.dumps(data)

# ✅ FIXED: Centralize the decision
class Order:
    def to_dict(self) -> dict:
        return {"id": self.id, "ts": self.timestamp.isoformat()}

class OrderService:
    def save(self, order):
        self.db.write(order.to_dict())

class OrderExporter:
    def export(self, order):
        return json.dumps(order.to_dict())
```

---

## 3. Temporal Decomposition

**What:** Code is organized by *when* things happen, not by *what information* they hide.

**Why:** Leads to information leakage—multiple modules must understand the same data.

**Smell:** Methods named `step1`, `step2`, or modules that mirror a sequence of operations.

```python
# 🚩 RED FLAG: Organized by execution order
class FileProcessor:
    def step1_read_file(self, path): ...        # Returns raw bytes
    def step2_decompress(self, data): ...       # Returns decompressed
    def step3_parse_header(self, data): ...     # Returns header
    def step4_extract_records(self, data): ...  # Returns records
    # Caller must know the order and intermediate formats

# ✅ FIXED: Organized by information hiding
class CompressedFile:
    """Hides compression format details."""
    def read(self, path) -> bytes: ...

class RecordFile:
    """Hides record format details."""
    def __init__(self, data: bytes): ...
    def get_records(self) -> list[Record]: ...
```

---

## 4. Overexposure

**What:** Using common features requires awareness of rarely-used features.

**Why:** Forces all callers to pay the cognitive cost of features they don't need.

**Smell:** Simple use cases require specifying many optional parameters.

```python
# 🚩 RED FLAG: Common case requires rare-case knowledge
def connect(
    host: str,
    port: int,
    ssl: bool = True,
    ssl_cert: str = None,        # Rarely needed
    ssl_verify: bool = True,     # Rarely needed
    proxy: str = None,           # Rarely needed
    proxy_auth: tuple = None,    # Rarely needed
    timeout: int = 30,
    retry_policy: RetryPolicy = None,  # Rarely needed
):
    pass

# ✅ FIXED: Common case is simple, rare cases use config object
def connect(host: str, port: int, timeout: int = 30) -> Connection:
    pass

def connect_with_options(host: str, port: int, options: ConnectionOptions) -> Connection:
    pass
```

---

## 5. Pass-Through Method

**What:** A method does nothing except forward arguments to another method.

**Why:** Adds a layer without adding value—pure complexity overhead.

**Smell:** Method body is essentially `return self.other.same_method(same_args)`.

```python
# 🚩 RED FLAG: Pass-through adds nothing
class UserController:
    def get_user(self, user_id: str) -> User:
        return self.user_service.get_user(user_id)

    def update_user(self, user_id: str, data: dict) -> User:
        return self.user_service.update_user(user_id, data)

# ✅ FIXED: Each layer transforms or adds value
class UserController:
    def get_user(self, request: Request) -> Response:
        user_id = self._extract_user_id(request)  # HTTP → domain
        self._check_permissions(request.auth, user_id)  # Adds authorization
        user = self.user_service.get_user(user_id)
        return Response(status=200, body=user.to_api_dict())  # Domain → HTTP
```

---

## 6. Repetition

**What:** Non-trivial code appears multiple times.

**Why:** Bugs must be fixed N times. Inconsistencies creep in. Maintenance multiplies.

**Smell:** Copy-paste patterns, similar-looking code blocks, "we do this everywhere."

```python
# 🚩 RED FLAG: Same pattern repeated
class OrderService:
    def create(self, data):
        if not self.db.is_connected():
            self.db.connect()
        try:
            return self.db.insert("orders", data)
        except DbError as e:
            logger.error(f"DB error: {e}")
            raise ServiceError(e)

    def update(self, id, data):
        if not self.db.is_connected():
            self.db.connect()
        try:
            return self.db.update("orders", id, data)
        except DbError as e:
            logger.error(f"DB error: {e}")
            raise ServiceError(e)

# ✅ FIXED: Extract the pattern
class OrderService:
    def _execute(self, operation: Callable):
        self.db.ensure_connected()
        try:
            return operation()
        except DbError as e:
            logger.error(f"DB error: {e}")
            raise ServiceError(e)

    def create(self, data):
        return self._execute(lambda: self.db.insert("orders", data))

    def update(self, id, data):
        return self._execute(lambda: self.db.update("orders", id, data))
```

---

## 7. Special-General Mixture

**What:** Special-purpose code is mixed into general-purpose modules.

**Why:** Pollutes reusable code with context-specific logic, reducing reusability.

**Smell:** Conditionals checking for specific cases in otherwise generic code.

```python
# 🚩 RED FLAG: General-purpose parser with special cases baked in
class JsonParser:
    def parse(self, text: str) -> dict:
        data = json.loads(text)
        # Special cases polluting general parser
        if "api_v1_response" in data:
            data = data["api_v1_response"]["payload"]
        if self.client_name == "acme_corp":
            data = self._apply_acme_transforms(data)
        return data

# ✅ FIXED: Separate general and special
class JsonParser:
    def parse(self, text: str) -> dict:
        return json.loads(text)

class AcmeApiClient:
    def __init__(self, parser: JsonParser): ...

    def parse_response(self, text: str) -> dict:
        data = self.parser.parse(text)
        payload = data["api_v1_response"]["payload"]
        return self._apply_acme_transforms(payload)
```

---

## 8. Conjoined Methods

**What:** Two methods are so intertwined you can't understand one without the other.

**Why:** Defeats modularity—changes ripple unpredictably, testing is painful.

**Smell:** Reading method A requires constantly jumping to method B and vice versa.

```python
# 🚩 RED FLAG: Conjoined—each depends on the other's internals
class Processor:
    def prepare(self, data):
        self._temp_buffer = []
        self._index_map = {}
        for i, item in enumerate(data):
            if self._should_include(item):  # Uses _pending from process()
                self._temp_buffer.append(item)
                self._index_map[item.id] = i

    def process(self):
        self._pending = set()
        for item in self._temp_buffer:  # Uses _temp_buffer from prepare()
            result = self._transform(item, self._index_map)  # Uses _index_map
            self._pending.add(result.id)

# ✅ FIXED: Self-contained methods with explicit data flow
class Processor:
    def prepare(self, data: list[Item]) -> PreparedBatch:
        items = [item for item in data if self._should_include(item)]
        return PreparedBatch(items)

    def process(self, batch: PreparedBatch) -> list[Result]:
        return [self._transform(item) for item in batch.items]
```

---

## 9. Comment Repeats Code

**What:** The comment says exactly what the code already says.

**Why:** Adds noise without information. Wastes reader's time. Becomes stale.

**Smell:** Comment could be deleted without losing any understanding.

```python
# 🚩 RED FLAG: Comments repeat the obvious
# Set count to zero
count = 0

# Loop through users
for user in users:
    # Check if user is active
    if user.is_active:
        # Increment count
        count += 1

# Return the count
return count

# ✅ FIXED: Comment adds non-obvious information (or remove entirely)
# Count excludes soft-deleted users who still have is_active=True
# due to the legacy migration. See JIRA-1234.
return sum(1 for u in users if u.is_active and not u.soft_deleted)
```

---

## 10. Implementation Documentation Contaminates Interface

**What:** Interface docs expose implementation details callers don't need.

**Why:** Couples users to implementation—changes break expectations, docs become lies.

**Smell:** Docs mention internal data structures, algorithms, or private methods.

```python
# 🚩 RED FLAG: Interface docs reveal implementation
class Cache:
    def get(self, key: str) -> Any:
        """
        Retrieve value from cache.

        Uses an LRU eviction policy with a doubly-linked list for O(1) access.
        The internal _hash_map stores node references. When accessed, nodes
        are moved to the head via _move_to_front(). If _size exceeds _capacity,
        _evict_tail() removes the least recently used entry.
        """
        pass

# ✅ FIXED: Interface docs describe behavior, not implementation
class Cache:
    def get(self, key: str) -> Any:
        """
        Retrieve a value from the cache.

        Returns None if key is not present or has been evicted.
        Accessing a key refreshes its position (least-recently-used keys
        are evicted first when capacity is reached).
        """
        pass
```

---

## 11. Vague Name

**What:** A name is so generic it conveys almost nothing.

**Why:** Reader must inspect usage or implementation to understand purpose.

**Smell:** Names like `data`, `info`, `temp`, `result`, `value`, `item`, `process`, `handle`.

```python
# 🚩 RED FLAG: Vague, uninformative names
def process(data):
    result = []
    for item in data:
        temp = handle(item)
        if check(temp):
            result.append(temp)
    return result

# ✅ FIXED: Names convey meaning
def filter_valid_transactions(transactions: list[Transaction]) -> list[Transaction]:
    valid = []
    for txn in transactions:
        normalized = normalize_currency(txn)
        if passes_fraud_check(normalized):
            valid.append(normalized)
    return valid
```

---

## 12. Hard to Pick Name

**What:** You struggle to find a clear, intuitive name for something.

**Why:** Naming difficulty often signals a design problem—unclear responsibility or mixed concerns.

**Smell:** Names become long compound phrases, or you keep renaming things.

```python
# 🚩 RED FLAG: Name is hard because responsibility is unclear
class UserOrderEmailNotificationAndInventoryManager:
    def process_user_action_and_maybe_send_email_or_update_stock(self, ...):
        pass
# Why is this hard to name? It does too many things.

# ✅ FIXED: Clear responsibilities → clear names
class OrderProcessor:
    def process(self, order: Order) -> None: ...

class InventoryService:
    def reserve(self, items: list[Item]) -> None: ...

class NotificationService:
    def send_order_confirmation(self, order: Order) -> None: ...
```

---

## 13. Hard to Describe

**What:** Documenting a variable or method requires lengthy explanation.

**Why:** If it's hard to describe, it's probably too complex or doing too much.

**Smell:** You need multiple paragraphs, many bullet points, or "it depends" explanations.

```python
# 🚩 RED FLAG: Requires essay to explain
def process(data, mode, flags):
    """
    Process data according to mode and flags.

    If mode is 'strict' and flags contains 'validate', performs full validation
    then processes. If mode is 'lenient' and flags contains 'validate', performs
    partial validation. If mode is 'strict' without 'validate', skips validation
    but applies strict parsing. If flags contains 'async', returns a Future
    unless mode is 'strict' and 'validate' is set, in which case it blocks.
    If flags contains 'cache', results are cached unless mode is 'lenient'
    and the data size exceeds 1MB. ...
    """
    pass

# ✅ FIXED: Simple to describe because it does one thing
def validate(data: Data, level: ValidationLevel) -> ValidationResult:
    """Check data against schema. Level controls strictness."""
    pass

def parse(data: Data, strict: bool = True) -> ParsedData:
    """Parse data into structured form. Strict mode rejects ambiguous input."""
    pass
```

---

## 14. Non-Obvious Code

**What:** Code's behavior or meaning isn't clear from reading it.

**Why:** Forces reader to simulate execution mentally, trace dependencies, or guess.

**Smell:** You have to "run it in your head" or read other files to understand it.

```python
# 🚩 RED FLAG: What does this do?
def f(x):
    return x and x[0] == x[-1] and (len(x) < 2 or f(x[1:-1]))

# Also non-obvious: hidden side effects
def get_user(id):
    user = cache.get(id) or db.fetch(id)
    cache.set(id, user)  # Hidden write in a "get"
    metrics.increment("user_fetched")  # Hidden side effect
    return user

# ✅ FIXED: Obvious from reading
def is_palindrome(text: str) -> bool:
    """Check if text reads the same forwards and backwards."""
    cleaned = text.lower().replace(" ", "")
    return cleaned == cleaned[::-1]

def get_user(id: str) -> User:
    """Retrieve user from cache or database. Does not modify cache."""
    return cache.get(id) or db.fetch(id)

def get_user_and_cache(id: str) -> User:
    """Retrieve user and update cache. Records metric."""
    user = get_user(id)
    cache.set(id, user)
    metrics.increment("user_fetched")
    return user
```

---

## Quick Reference Checklist

When reviewing code, watch for these red flags:

| # | Red Flag | Question |
|---|----------|----------|
| 1 | Shallow Module | Is the interface as complex as the implementation? |
| 2 | Information Leakage | Does this decision appear in multiple places? |
| 3 | Temporal Decomposition | Is this organized by *when* instead of *what info*? |
| 4 | Overexposure | Must common cases know about rare features? |
| 5 | Pass-Through Method | Does this just forward to another method? |
| 6 | Repetition | Have I seen this pattern elsewhere? |
| 7 | Special-General Mixture | Is special-case logic polluting general code? |
| 8 | Conjoined Methods | Can I understand this without reading another method? |
| 9 | Comment Repeats Code | Does this comment add any information? |
| 10 | Implementation in Interface Docs | Do these docs expose internals? |
| 11 | Vague Name | Would a new reader know what this is? |
| 12 | Hard to Pick Name | Why is naming this so difficult? |
| 13 | Hard to Describe | Why does explaining this require so much text? |
| 14 | Non-Obvious Code | Can I understand this without tracing execution? |

---

## Red Flag → Root Cause Mapping

| Red Flag | Often Indicates |
|----------|-----------------|
| Shallow Module | Module boundary in wrong place |
| Information Leakage | Missing abstraction to centralize decision |
| Temporal Decomposition | Organized by workflow instead of information |
| Overexposure | Interface not designed for common case |
| Pass-Through | Unnecessary layer; should merge or differentiate |
| Repetition | Missing helper/abstraction |
| Special-General Mixture | Concerns not separated |
| Conjoined Methods | Should be merged or restructured |
| Comment Repeats Code | Bad naming or unnecessary comment |
| Implementation Docs | Leaky abstraction |
| Vague Name | Unclear purpose; may need redesign |
| Hard to Pick Name | Muddled responsibilities |
| Hard to Describe | Doing too much; needs decomposition |
| Non-Obvious Code | Needs refactoring or better naming |
