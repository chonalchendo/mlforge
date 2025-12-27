# Ousterhout's 15 Design Principles
*From "A Philosophy of Software Design" — Code Review Reference*

---

## Agent Workflow

When analysing code against these design principles, follow this workflow:

### Step 1: Discover and Map the Codebase
```
1. List all modules/packages in the target directory (e.g., src/mlforge/)
2. Identify the module hierarchy and dependencies
3. Note the apparent architectural layers (e.g., API, service, data, utils)
4. Count approximate lines of code per module to gauge complexity distribution
```

### Step 2: Analyse Module Depth (Principles 4, 6, 7)
```
For each significant module/class:
- Count public methods/functions (interface size)
- Estimate implementation complexity (LOC, cyclomatic complexity)
- Calculate depth ratio: functionality ÷ interface complexity
- Flag shallow modules (interface ≈ implementation complexity)
- Flag overly specific modules that could be generalised
```

### Step 3: Analyse Interface Design (Principles 5, 10)
```
For public APIs and commonly-used functions:
- Check if common use cases require minimal parameters
- Identify if callers must handle complexity that could be internal
- Look for sensible defaults vs required configuration
- Note any "complexity pushed upward" patterns
```

### Step 4: Check Abstraction Layers (Principles 8, 9)
```
Trace a typical request/operation through layers:
- Does each layer provide a meaningful abstraction change?
- Are there pass-through layers adding no value?
- Is general-purpose code separated from special-purpose code?
- Are business rules mixed with infrastructure concerns?
```

### Step 5: Evaluate Error Handling (Principle 11)
```
Review error handling patterns:
- Are there errors that could be "defined out of existence"?
- Do APIs force callers to handle cases the module could handle?
- Are exceptions used for flow control vs actual errors?
```

### Step 6: Assess Documentation Quality (Principles 13, 14)
```
Sample docstrings and comments:
- Do comments explain "why" not "what"?
- Is code self-documenting through clear naming?
- Are there complex sections lacking explanation?
- Is the code optimised for reading or writing?
```

### Step 7: Look for Design Investment (Principles 1, 2, 3, 12, 15)
```
Assess overall design health:
- Signs of incremental complexity accumulation?
- Evidence of refactoring and continuous improvement?
- Are features built on clean abstractions or tangled together?
- Does the code show signs of "design it twice" thinking?
```

### Step 8: Generate Report
```
Structure the output as:

## Summary
[2-3 sentences on overall design health]

## Strengths
[Principles the codebase follows well, with specific examples]

## Areas for Improvement
[Principles being violated, with specific file:line references]

## Priority Recommendations
[Top 3-5 actionable improvements, ordered by impact]

## Detailed Findings
[Principle-by-principle breakdown with code references]
```

### Analysis Parameters
- **Target directory**: Specified by user (e.g., `src/mlforge/`)
- **Depth**: Analyse all `.py` files recursively
- **Focus areas**: Prioritise public interfaces and frequently-imported modules
- **Output format**: Markdown report saved to specified location

---

## The 15 Design Principles

---

## 1. Complexity is Incremental

**What:** Complexity isn't added all at once—it accumulates through countless small decisions.

**Why:** No single "bad" decision kills a codebase. Death by a thousand cuts.

**How:** Treat every addition as a potential complexity debt. Ask: "Is this making things harder to understand or modify?"

```python
# ❌ Each small shortcut adds up
def process(d, t, f=True, x=None, retry=3, v=False):
    pass

# ✅ Resist incremental complexity
@dataclass
class ProcessConfig:
    timeout: int
    validate: bool = True
    max_retries: int = 3

def process(data: bytes, config: ProcessConfig) -> Result:
    pass
```

---

## 2. Working Code Isn't Enough

**What:** Code that "works" but is hard to understand or modify is not done.

**Why:** Most of a codebase's lifetime is spent being read and modified, not written.

**How:** Refactor until the design is clean, not just until tests pass.

```python
# ❌ Works, but what does it do?
def calc(u, p):
    return sum(i['a'] * i['q'] for i in u.c if i['s'] == 'a') * (1 - p/100)

# ✅ Clear intent, maintainable
def calculate_order_total(user: User, discount_percent: float) -> Decimal:
    active_items = [item for item in user.cart if item.status == ItemStatus.ACTIVE]
    subtotal = sum(item.price * item.quantity for item in active_items)
    return subtotal * (1 - discount_percent / 100)
```

---

## 3. Make Continual Small Investments

**What:** Improve design incrementally with every change—don't wait for a big rewrite.

**Why:** Big rewrites rarely happen. Small improvements compound.

**How:** Leave code cleaner than you found it. Budget 10-20% of each task for cleanup.

```python
# While fixing a bug, also clean up what you touch
# Before: You found this mess
def get_data(id, db, cache, log, retry=True):
    # 200 lines of tangled logic
    pass

# After: Extract one piece, improve naming
def get_data(user_id: str, repository: DataRepository) -> UserData:
    cached = repository.get_cached(user_id)
    if cached:
        return cached
    return repository.fetch_and_cache(user_id)
```

---

## 4. Modules Should Be Deep

**What:** Best modules have small, simple interfaces but powerful functionality.

**Why:** Deep modules hide complexity. Shallow modules spread it everywhere.

**How:** Maximize the ratio of functionality to interface complexity.

```python
# ❌ Shallow: Interface mirrors implementation
class ShallowFileReader:
    def open(self, path): ...
    def read_header(self): ...
    def read_chunk(self, size): ...
    def decode_chunk(self, chunk): ...
    def close(self): ...

# ✅ Deep: Simple interface, complex implementation hidden
class DeepFileReader:
    def read(self, path: str) -> Content:
        """Handles opening, chunking, decoding, errors, cleanup internally."""
        pass
```

---

## 5. Interfaces Should Make Common Usage Simple

**What:** Design for the 90% case. Common operations should be trivial.

**Why:** If common cases require ceremony, the interface is backwards.

**How:** Study actual usage patterns. Optimize the interface for what's frequent.

```python
# ❌ Common case requires too much setup
client = HttpClient()
client.set_timeout(30)
client.set_retries(3)
client.set_headers({'Accept': 'application/json'})
response = client.execute(Request('GET', url))

# ✅ Common case is one line, complex cases still possible
response = http.get(url)  # Sensible defaults
response = http.get(url, timeout=60, headers=custom_headers)  # When needed
```

---

## 6. Simple Interface > Simple Implementation

**What:** Push complexity into the implementation, not the interface.

**Why:** One complex implementation beats many complex call sites.

**How:** If you're choosing where to put complexity, hide it inside the module.

```python
# ❌ Simple implementation, complex interface
def save_user(user, validate=True, hash_pw=True, notify=True,
              retry=True, log=True, transaction=None):
    if validate: ...
    if hash_pw: ...
    # Caller must understand all flags

# ✅ Complex implementation, simple interface
def save_user(user: User) -> None:
    """Validates, hashes password, notifies, retries, logs—all handled."""
    pass  # Complexity lives here, not at call sites
```

---

## 7. General-Purpose Modules Are Deeper

**What:** Somewhat general interfaces serve more use cases with less surface area.

**Why:** Overly specific modules proliferate and fragment the codebase.

**How:** Ask "What's the general problem?" not "What's my immediate need?"

```python
# ❌ Too specific—you'll need another one tomorrow
def send_welcome_email_to_new_premium_subscriber(user, plan):
    pass

# ✅ General purpose—covers many cases
class EmailService:
    def send(self, template: str, recipient: str, context: dict) -> None:
        pass

# Usage: email_service.send("welcome", user.email, {"plan": plan.name})
```

---

## 8. Separate General-Purpose and Special-Purpose Code

**What:** Don't pollute general modules with special cases.

**Why:** Special cases make general code fragile and hard to reuse.

**How:** Push special cases up to callers or into dedicated special-case modules.

```python
# ❌ General code polluted with special cases
class TextEditor:
    def format(self, text):
        if self.is_legal_document:  # Special case leaked in
            text = self._add_legal_headers(text)
        if self.is_medical_record:  # Another special case
            text = self._redact_phi(text)
        return self._apply_formatting(text)

# ✅ Clean separation
class TextEditor:
    def format(self, text: str) -> str:
        return self._apply_formatting(text)

class LegalDocumentEditor:
    def __init__(self, editor: TextEditor): ...
    def format(self, text: str) -> str:
        return self.editor.format(self._add_legal_headers(text))
```

---

## 9. Different Layers Should Have Different Abstractions

**What:** Each layer should provide a distinct transformation of abstraction.

**Why:** Pass-through layers add complexity without value.

**How:** If a layer just forwards calls, it shouldn't exist.

```python
# ❌ Pass-through layers (no abstraction change)
class UserController:
    def get_user(self, id): return self.service.get_user(id)
class UserService:
    def get_user(self, id): return self.repo.get_user(id)
class UserRepository:
    def get_user(self, id): return self.db.query(...)

# ✅ Each layer transforms the abstraction
class UserController:       # HTTP concepts: requests, responses, status codes
    def get_user(self, request): ...
class UserService:          # Business concepts: validation, permissions, rules
    def get_user_with_permissions(self, user_id, requester): ...
class UserRepository:       # Persistence concepts: queries, caching, connections
    def find_by_id(self, id): ...
```

---

## 10. Pull Complexity Downward

**What:** Handle complexity at lower levels so higher levels stay simple.

**Why:** Low-level code is written once; high-level code is written many times.

**How:** Make the hard decisions in the implementation, not at call sites.

```python
# ❌ Complexity pushed up to every caller
config_path = os.environ.get('CONFIG_PATH', 'config.yaml')
if not os.path.exists(config_path):
    config_path = os.path.expanduser('~/.myapp/config.yaml')
config = yaml.safe_load(open(config_path))
if 'database' not in config:
    raise ConfigError("Missing database config")

# ✅ Complexity pulled down into module
config = Config.load()  # Handles paths, defaults, validation internally
```

---

## 11. Define Errors Out of Existence

**What:** Design APIs where error conditions simply can't occur.

**Why:** Every error case is complexity that propagates through callers.

**How:** Change semantics so the "error" becomes a valid, handled case.

```python
# ❌ Caller must handle missing key
value = cache.get(key)
if value is None:
    # Is it missing or actually None? Must check separately
    if key not in cache:
        value = compute_expensive()
        cache.set(key, value)

# ✅ Error defined out of existence
value = cache.get_or_compute(key, compute_expensive)
# Never raises, never returns "missing"—always returns a value
```

---

## 12. Design It Twice

**What:** Consider at least two fundamentally different approaches before committing.

**Why:** Your first idea is rarely the best. Comparison reveals tradeoffs.

**How:** Sketch alternatives quickly. Compare interfaces, not just implementations.

```python
# Approach A: Event-based
class OrderProcessor:
    def process(self, order):
        self.emit('order.validated', order)
        self.emit('order.charged', order)
        self.emit('order.fulfilled', order)

# Approach B: Pipeline-based
class OrderPipeline:
    def __init__(self, steps: list[Step]): ...
    def process(self, order):
        return reduce(lambda o, step: step(o), self.steps, order)

# Compare: Which is easier to test? Extend? Debug? Monitor?
# Then choose—or find a third approach that combines the best of both.
```

---

## 13. Comments Should Describe Non-Obvious Things

**What:** Don't narrate code. Explain *why*, not *what*.

**Why:** Good comments capture knowledge that can't be expressed in code.

**How:** Comment rationale, constraints, non-obvious effects, and design decisions.

```python
# ❌ Narrates the obvious
# Loop through users and check if active
for user in users:
    if user.is_active:  # Check if user is active
        process(user)   # Process the user

# ✅ Explains the non-obvious
# Process oldest first to prevent starvation of long-waiting users.
# We skip recently active users (< 5 min) because they're likely
# still in another pipeline stage due to eventual consistency.
for user in sorted(users, key=lambda u: u.last_activity):
    if user.minutes_since_active > 5:
        process(user)
```

---

## 14. Design for Reading, Not Writing

**What:** Optimize code for the reader, not the writer.

**Why:** Code is read 10x more than it's written. Writing is a one-time cost.

**How:** Choose clarity over brevity. Spend extra time to save readers time.

```python
# ❌ Clever, fast to write, slow to read
result = {k: v for d in [a, b, c] for k, v in d.items() if k not in x and v}

# ✅ Clear, slower to write, fast to read
result = {}
for source in [defaults, user_config, overrides]:
    for key, value in source.items():
        if key not in excluded_keys and value is not None:
            result[key] = value
```

---

## 15. Increments Should Be Abstractions, Not Features

**What:** Build the system as layers of clean abstractions, not feature by feature.

**Why:** Feature-driven development creates tangled dependencies. Abstraction-driven development creates composable building blocks.

**How:** Ask "What abstraction does this feature need?" Build that first.

```python
# ❌ Feature-driven: Each feature tangles with others
def send_invoice():
    # Email logic + PDF logic + payment logic + notification logic
    # All intertwined in one feature

# ✅ Abstraction-driven: Features compose clean abstractions
class PdfGenerator: ...      # Abstraction: document generation
class EmailService: ...      # Abstraction: communication
class PaymentGateway: ...    # Abstraction: payments
class NotificationHub: ...   # Abstraction: notifications

def send_invoice(order):     # Feature: thin layer composing abstractions
    pdf = pdf_generator.create_invoice(order)
    email_service.send(order.customer.email, attachment=pdf)
    notification_hub.notify(order.customer, "Invoice sent")
```

---

## Quick Reference Checklist

When reviewing code, ask:

| # | Principle | Question |
|---|-----------|----------|
| 1 | Complexity is incremental | Is this change adding subtle complexity? |
| 2 | Working code isn't enough | Is this clear and maintainable, or just "working"? |
| 3 | Continual investment | Did we leave this cleaner than we found it? |
| 4 | Deep modules | Is the interface small relative to functionality? |
| 5 | Simple common usage | Is the common case trivial to write? |
| 6 | Simple interface over impl | Is complexity hidden inside, not pushed to callers? |
| 7 | General-purpose depth | Is this general enough without over-engineering? |
| 8 | Separate concerns | Are special cases leaking into general code? |
| 9 | Layer abstraction | Does each layer provide a meaningful transformation? |
| 10 | Pull complexity down | Are callers doing work the module should handle? |
| 11 | Define errors out | Can we change the design so this error can't happen? |
| 12 | Design it twice | Did we consider alternatives? |
| 13 | Non-obvious comments | Do comments explain *why*, not *what*? |
| 14 | Design for reading | Would a new reader understand this quickly? |
| 15 | Abstractions over features | Are we building composable blocks or tangled features? |
