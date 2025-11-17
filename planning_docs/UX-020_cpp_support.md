# UX-020: Add C/C++ Support

## TODO Reference
- TODO.md: "UX-020: Add C/C++ Support (~3 days)"
- High priority for systems engineers
- Follow patterns from existing language parsers

## Objective
Add comprehensive C/C++ support to the code indexer, including tree-sitter integration, function/class/struct extraction, and proper semantic unit indexing.

## Current State
- Rust parser supports: Python, JavaScript, TypeScript, Java, Go, Rust
- File extensions: .py, .js, .jsx, .ts, .tsx, .java, .go, .rs
- Parser uses tree-sitter with language-specific queries for functions and classes
- C/C++ not currently supported

## Implementation Plan

### Phase 1: Dependencies & Setup
- [ ] Add tree-sitter-cpp to Cargo.toml
- [ ] Add tree-sitter-cpp to requirements.txt (Python bindings)
- [ ] Update Rust parsing.rs to include C++ language support

### Phase 2: Rust Parser Implementation
- [ ] Add C and Cpp variants to SupportedLanguage enum
- [ ] Map file extensions (.c, .cc, .cpp, .cxx, .h, .hpp, .hxx)
- [ ] Implement get_language() for C/C++
- [ ] Create function_query() for C/C++ (function_definition)
- [ ] Create class_query() for C/C++ (class_specifier, struct_specifier)
- [ ] Initialize parsers for C and C++ in CodeParser::new()

### Phase 3: Python Integration
- [ ] Update IncrementalIndexer.SUPPORTED_EXTENSIONS with C/C++ extensions
- [ ] Ensure language mapping works for C/C++ files

### Phase 4: Testing
- [ ] Create test_cpp_parsing.py with sample C/C++ code
- [ ] Test function extraction (regular functions, member functions)
- [ ] Test class extraction
- [ ] Test struct extraction
- [ ] Test header files (.h, .hpp)
- [ ] Test various C++ features (templates, namespaces, etc.)
- [ ] Run full test suite

### Phase 5: Documentation
- [ ] Update CHANGELOG.md
- [ ] Update README.md supported languages list
- [ ] Add C/C++ to language capabilities

## Progress Tracking

### Phase 1: Dependencies & Setup
- [x] Added tree-sitter-cpp to Cargo.toml
- [x] Added tree-sitter-cpp to requirements.txt

### Phase 2: Rust Parser Implementation
- [x] Added C and Cpp to SupportedLanguage enum
- [x] Mapped all C/C++ file extensions
- [x] Implemented get_language() for C/C++
- [x] Created function_query() for C/C++
- [x] Created class_query() for C/C++ (structs and classes)
- [x] Initialized parsers in CodeParser::new()

### Phase 3: Python Integration
- [x] Updated IncrementalIndexer.SUPPORTED_EXTENSIONS
- [x] Updated language mapping in fallback parser

### Phase 4: Testing
- [x] Created test_cpp_parsing.py with 19 comprehensive tests
- [x] All tests passing ✅

### Phase 5: Documentation
- [x] Updated CHANGELOG.md
- [x] Updated README.md
- [x] Updated language lists in diagrams

## Notes & Decisions

### Tree-Sitter C/C++ Queries
The tree-sitter-cpp grammar uses these key node types:
- `function_definition` - for function declarations
- `class_specifier` - for C++ classes
- `struct_specifier` - for C/C++ structs
- `declaration` - for variable and function declarations

### File Extensions
C/C++ uses multiple extensions:
- C: `.c`, `.h`
- C++: `.cpp`, `.cc`, `.cxx`, `.hpp`, `.hxx`, `.hh`

We'll support all common extensions to maximize coverage.

## Test Cases

### Sample C Code
```c
#include <stdio.h>

struct Point {
    int x;
    int y;
};

int add(int a, int b) {
    return a + b;
}

void print_point(struct Point p) {
    printf("(%d, %d)\n", p.x, p.y);
}
```

### Sample C++ Code
```cpp
#include <iostream>
#include <string>

class Calculator {
private:
    double result;

public:
    Calculator() : result(0.0) {}

    double add(double a, double b) {
        result = a + b;
        return result;
    }

    double getResult() const {
        return result;
    }
};

namespace Math {
    int multiply(int a, int b) {
        return a * b;
    }
}
```

## Code Snippets

### Rust Query Pattern (to be implemented)
```rust
// For C/C++ functions
r#"
(function_definition
  declarator: (function_declarator
    declarator: (_) @name) @declarator
  body: (compound_statement) @body) @function
"#

// For C++ classes
r#"
(class_specifier
  name: (type_identifier) @name
  body: (field_declaration_list) @body) @class
"#

// For C/C++ structs
r#"
(struct_specifier
  name: (type_identifier) @name
  body: (field_declaration_list) @body) @class
"#
```

## Blockers
- None identified yet

## Next Steps After Completion
- Consider adding template specialization support (FEAT-005)
- Consider adding namespace hierarchy tracking
- Consider adding C++17/C++20 specific features

## Completion Summary

**Status:** ✅ Complete
**Date:** 2025-11-17
**Implementation Time:** ~2 hours

### What Was Built
- Full C and C++ language support in the Rust parser
- Support for all common C/C++ file extensions (.c, .h, .cpp, .cc, .cxx, .hpp, .hxx, .hh)
- Function extraction for both C and C++ code
- Class/struct extraction (struct_specifier for C, class_specifier for C++)
- Comprehensive test suite with 19 tests covering all aspects

### Impact
- Systems engineers can now index and search C/C++ codebases
- Supports both C and C++ with appropriate language-specific handling
- Maintains same 1-6ms parsing performance per file
- All tests passing (19/19) ✅

### Files Changed
- `rust_core/Cargo.toml` - Added tree-sitter-cpp dependency
- `requirements.txt` - Added tree-sitter-cpp Python bindings
- `rust_core/src/parsing.rs` - Added C and Cpp language support
- `src/memory/incremental_indexer.py` - Added C/C++ file extensions
- `tests/unit/test_cpp_parsing.py` - Created comprehensive test suite (NEW)
- `CHANGELOG.md` - Documented changes
- `README.md` - Updated supported languages

### Test Results
```
19 tests in test_cpp_parsing.py - ALL PASSING ✅
- 4 C parsing tests
- 4 C++ parsing tests
- 8 file extension tests
- 3 semantic unit validation tests
```

### Technical Decisions
1. **Unified tree-sitter-cpp library:** Both C and C++ use the same tree-sitter library but with language-specific queries
2. **Separate language variants:** C and Cpp are distinct enums to allow for future language-specific features
3. **Extension mapping:** `.h` files default to C (common convention), but this works for C++ headers too
4. **Query design:** Used simple, robust queries that capture the most common code structures

### Known Limitations
- C++ templates are captured but not specially processed (enhancement for FEAT-005)
- Namespace hierarchy is not tracked (future enhancement)
- Modern C++ features (C++17/20) are parsed but not categorized separately

### Next Steps
- Continue with UX-021 (SQL Support)
- Return to FEAT-005 for enhanced C++ template/namespace support
