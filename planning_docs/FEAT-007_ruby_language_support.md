# FEAT-007: Ruby Language Support

## TODO Reference
- TODO.md: "Add support for Ruby (~3 days)"
  - tree-sitter-ruby integration
  - Method, class, module extraction

## Objective
Add Ruby as a supported language for code indexing and semantic search, bringing total language support from 12 to 13 file formats.

## Current State
Currently supported languages:
- **9 programming languages**: Python, JS, TS, Java, Go, Rust, C, C++, C#, SQL
- **3 config formats**: JSON, YAML, TOML
- Total: 12 file formats

Ruby is missing despite being widely used in web development (Rails), scripting, and DevOps (Chef, Puppet).

## Implementation Plan

### Phase 1: Rust Module Updates
- [ ] Add `tree-sitter-ruby = "0.23"` dependency to `rust_core/Cargo.toml`
- [ ] Add `Ruby` variant to `SupportedLanguage` enum in `rust_core/src/parsing.rs`
- [ ] Add `.rb` extension mapping in `from_extension()` method
- [ ] Add Ruby language parser in `get_language()` method
- [ ] Add Ruby function/method query pattern in `function_query()` method
- [ ] Add Ruby class query pattern in `class_query()` method
- [ ] Add Ruby module query support (Ruby-specific feature)

### Phase 2: Python Module Updates (if needed)
- [ ] Check `src/memory/code_parser.py` for language lists
- [ ] Check `src/memory/python_parser.py` fallback parser
- [ ] Update any language validation or mapping code

### Phase 3: Testing
- [ ] Create `tests/unit/test_ruby_parsing.py` with comprehensive tests
- [ ] Test method extraction from Ruby files
- [ ] Test class extraction from Ruby files
- [ ] Test module extraction from Ruby files
- [ ] Test file extension recognition
- [ ] Create sample Ruby files for testing

### Phase 4: Documentation
- [ ] Update `docs/API.md` language count (12 → 13)
- [ ] Update `CHANGELOG.md` with FEAT-007 entry
- [ ] Update `CLAUDE.md` metrics if needed
- [ ] Update `README.md` if it lists supported languages

## Ruby Tree-Sitter Query Patterns

Based on tree-sitter-ruby grammar, the query patterns needed:

### Methods
```ruby
def method_name(param1, param2)
  # body
end
```
Query pattern:
```scheme
(method
  name: (identifier) @name
  parameters: (method_parameters)? @params
  body: (_)* @body) @function
```

### Classes
```ruby
class ClassName
  # body
end
```
Query pattern:
```scheme
(class
  name: (constant) @name
  body: (_)* @body) @class
```

### Modules
```ruby
module ModuleName
  # body
end
```
Query pattern:
```scheme
(module
  name: (constant) @name
  body: (_)* @body) @module
```

## Progress Tracking
- [ ] Cargo.toml updated
- [ ] parsing.rs updated with Ruby support
- [ ] Python code updated (if needed)
- [ ] Tests created and passing
- [ ] Documentation updated
- [ ] Commit and merge

## Notes & Decisions

### Decision: Ruby File Extensions
- Primary: `.rb` (standard Ruby files)
- Not including: `.erb` (embedded Ruby templates) - would require special handling
- Not including: `.rake`, `.gemspec` - these are Ruby but typically don't need indexing

### Decision: Module Support
Ruby has both classes and modules. Modules are important in Ruby for:
- Namespacing
- Mixins
- Organizing code

We should support module extraction in addition to classes and methods.

## Test Cases
1. **Method extraction**:
   - Instance methods
   - Class methods
   - Methods with parameters
   - Methods without parameters
   - Methods with default parameters

2. **Class extraction**:
   - Simple classes
   - Classes with inheritance
   - Nested classes

3. **Module extraction**:
   - Simple modules
   - Nested modules
   - Modules with methods

4. **File recognition**:
   - `.rb` extension recognized
   - Proper language identification

## Example Ruby Test File
```ruby
module MyModule
  class MyClass
    def instance_method(param1, param2 = "default")
      puts "Hello from instance method"
    end

    def self.class_method
      puts "Hello from class method"
    end
  end

  module NestedModule
    def helper_method
      puts "Helper method"
    end
  end
end
```
