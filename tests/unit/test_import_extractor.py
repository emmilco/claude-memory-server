"""Tests for import extraction functionality."""

import pytest
from src.memory.import_extractor import (
    ImportExtractor,
    ImportType,
    build_dependency_metadata,
)


@pytest.fixture
def extractor():
    """Create an import extractor instance."""
    return ImportExtractor()


class TestPythonImports:
    """Test Python import extraction."""

    def test_simple_import(self, extractor):
        """Test simple import statement."""
        code = "import os"
        imports = extractor.extract_imports("test.py", code, "python")

        assert len(imports) == 1
        assert imports[0].imported_module == "os"
        assert imports[0].import_type == ImportType.IMPORT
        assert imports[0].imported_items == []
        assert imports[0].line_number == 1

    def test_import_with_alias(self, extractor):
        """Test import with alias."""
        code = "import numpy as np"
        imports = extractor.extract_imports("test.py", code, "python")

        assert len(imports) == 1
        assert imports[0].imported_module == "numpy"
        assert imports[0].alias == "np"
        assert imports[0].import_type == ImportType.IMPORT

    def test_from_import(self, extractor):
        """Test from...import statement."""
        code = "from pathlib import Path"
        imports = extractor.extract_imports("test.py", code, "python")

        assert len(imports) == 1
        assert imports[0].imported_module == "pathlib"
        assert imports[0].imported_items == ["Path"]
        assert imports[0].import_type == ImportType.FROM_IMPORT

    def test_from_import_multiple(self, extractor):
        """Test from...import with multiple items."""
        code = "from typing import List, Dict, Optional"
        imports = extractor.extract_imports("test.py", code, "python")

        assert len(imports) == 1
        assert imports[0].imported_module == "typing"
        assert set(imports[0].imported_items) == {"List", "Dict", "Optional"}
        assert imports[0].import_type == ImportType.FROM_IMPORT

    def test_from_import_with_alias(self, extractor):
        """Test from...import with alias."""
        code = "from collections import OrderedDict as OD"
        imports = extractor.extract_imports("test.py", code, "python")

        assert len(imports) == 1
        assert imports[0].imported_module == "collections"
        assert imports[0].imported_items == ["OrderedDict"]
        assert imports[0].import_type == ImportType.FROM_IMPORT

    def test_relative_import(self, extractor):
        """Test relative imports."""
        code = "from . import helpers"
        imports = extractor.extract_imports("test.py", code, "python")

        assert len(imports) == 1
        assert imports[0].imported_module == "."
        assert imports[0].is_relative is True
        assert imports[0].imported_items == ["helpers"]

    def test_relative_import_parent(self, extractor):
        """Test parent directory relative import."""
        code = "from ..utils import logger"
        imports = extractor.extract_imports("test.py", code, "python")

        assert len(imports) == 1
        assert imports[0].imported_module == "..utils"
        assert imports[0].is_relative is True
        assert imports[0].imported_items == ["logger"]

    def test_wildcard_import(self, extractor):
        """Test wildcard import."""
        code = "from os import *"
        imports = extractor.extract_imports("test.py", code, "python")

        assert len(imports) == 1
        assert imports[0].imported_module == "os"
        assert imports[0].imported_items == ["*"]

    def test_multiple_imports(self, extractor):
        """Test multiple import statements."""
        code = """
import os
import sys
from pathlib import Path
from typing import List, Dict
"""
        imports = extractor.extract_imports("test.py", code, "python")

        assert len(imports) == 4
        modules = [imp.imported_module for imp in imports]
        assert "os" in modules
        assert "sys" in modules
        assert "pathlib" in modules
        assert "typing" in modules

    def test_ignores_comments(self, extractor):
        """Test that comments are ignored."""
        code = """
# import fake
import os
# from typing import Fake
"""
        imports = extractor.extract_imports("test.py", code, "python")

        assert len(imports) == 1
        assert imports[0].imported_module == "os"


class TestJavaScriptImports:
    """Test JavaScript/TypeScript import extraction."""

    def test_default_import(self, extractor):
        """Test default import."""
        code = "import React from 'react'"
        imports = extractor.extract_imports("test.js", code, "javascript")

        assert len(imports) == 1
        assert imports[0].imported_module == "react"
        assert imports[0].imported_items == ["React"]
        assert imports[0].import_type == ImportType.IMPORT

    def test_named_imports(self, extractor):
        """Test named imports."""
        code = "import { useState, useEffect } from 'react'"
        imports = extractor.extract_imports("test.js", code, "javascript")

        assert len(imports) == 1
        assert imports[0].imported_module == "react"
        assert set(imports[0].imported_items) == {"useState", "useEffect"}

    def test_namespace_import(self, extractor):
        """Test namespace import (import *)."""
        code = "import * as utils from './utils'"
        imports = extractor.extract_imports("test.js", code, "javascript")

        assert len(imports) == 1
        assert imports[0].imported_module == "./utils"
        assert imports[0].imported_items == ["*"]
        assert imports[0].is_relative is True

    def test_require_statement(self, extractor):
        """Test CommonJS require."""
        code = "const fs = require('fs')"
        imports = extractor.extract_imports("test.js", code, "javascript")

        assert len(imports) == 1
        assert imports[0].imported_module == "fs"
        assert imports[0].import_type == ImportType.REQUIRE

    def test_dynamic_import(self, extractor):
        """Test dynamic import."""
        code = "const module = await import('./module')"
        imports = extractor.extract_imports("test.js", code, "javascript")

        assert len(imports) == 1
        assert imports[0].imported_module == "./module"
        assert imports[0].import_type == ImportType.DYNAMIC_IMPORT

    def test_relative_import(self, extractor):
        """Test relative import paths."""
        code = "import { helper } from '../utils/helper'"
        imports = extractor.extract_imports("test.js", code, "javascript")

        assert len(imports) == 1
        assert imports[0].imported_module == "../utils/helper"
        assert imports[0].is_relative is True

    def test_mixed_imports(self, extractor):
        """Test mix of import types."""
        code = """
import React from 'react'
import { useState } from 'react'
const fs = require('fs')
"""
        imports = extractor.extract_imports("test.js", code, "javascript")

        assert len(imports) == 3
        types = [imp.import_type for imp in imports]
        assert ImportType.IMPORT in types
        assert ImportType.REQUIRE in types


class TestJavaImports:
    """Test Java import extraction."""

    def test_simple_import(self, extractor):
        """Test simple Java import."""
        code = "import java.util.List;"
        imports = extractor.extract_imports("Test.java", code, "java")

        assert len(imports) == 1
        assert imports[0].imported_module == "java.util"
        assert imports[0].imported_items == ["List"]
        assert imports[0].is_relative is False

    def test_wildcard_import(self, extractor):
        """Test wildcard import."""
        code = "import java.util.*;"
        imports = extractor.extract_imports("Test.java", code, "java")

        assert len(imports) == 1
        assert imports[0].imported_module == "java.util"
        assert imports[0].imported_items == ["*"]

    def test_static_import(self, extractor):
        """Test static import."""
        code = "import static java.lang.Math.PI;"
        imports = extractor.extract_imports("Test.java", code, "java")

        assert len(imports) == 1
        assert "java.lang" in imports[0].imported_module

    def test_multiple_imports(self, extractor):
        """Test multiple Java imports."""
        code = """
import java.util.List;
import java.util.Map;
import java.io.File;
"""
        imports = extractor.extract_imports("Test.java", code, "java")

        assert len(imports) == 3
        modules = [imp.imported_module for imp in imports]
        assert "java.util" in modules
        assert "java.io" in modules


class TestGoImports:
    """Test Go import extraction."""

    def test_single_import(self, extractor):
        """Test single Go import."""
        code = 'import "fmt"'
        imports = extractor.extract_imports("test.go", code, "go")

        assert len(imports) == 1
        assert imports[0].imported_module == "fmt"

    def test_import_with_alias(self, extractor):
        """Test import with alias."""
        code = 'import f "fmt"'
        imports = extractor.extract_imports("test.go", code, "go")

        assert len(imports) == 1
        assert imports[0].imported_module == "fmt"
        assert imports[0].alias == "f"

    def test_import_block(self, extractor):
        """Test import block."""
        code = """
import (
    "fmt"
    "os"
    "path/filepath"
)
"""
        imports = extractor.extract_imports("test.go", code, "go")

        assert len(imports) == 3
        modules = [imp.imported_module for imp in imports]
        assert "fmt" in modules
        assert "os" in modules
        assert "path/filepath" in modules

    def test_import_block_with_alias(self, extractor):
        """Test import block with aliases."""
        code = """
import (
    f "fmt"
    "os"
)
"""
        imports = extractor.extract_imports("test.go", code, "go")

        assert len(imports) == 2
        fmt_import = [imp for imp in imports if imp.imported_module == "fmt"][0]
        assert fmt_import.alias == "f"


class TestRustImports:
    """Test Rust import extraction."""

    def test_simple_use(self, extractor):
        """Test simple use statement."""
        code = "use std::collections::HashMap;"
        imports = extractor.extract_imports("test.rs", code, "rust")

        assert len(imports) == 1
        assert imports[0].imported_module == "std::collections::HashMap"
        assert imports[0].import_type == ImportType.USE

    def test_use_with_braces(self, extractor):
        """Test use with braces."""
        code = "use std::collections::{HashMap, HashSet};"
        imports = extractor.extract_imports("test.rs", code, "rust")

        assert len(imports) == 1
        assert imports[0].imported_module == "std::collections"
        assert set(imports[0].imported_items) == {"HashMap", "HashSet"}

    def test_crate_import(self, extractor):
        """Test crate-relative import."""
        code = "use crate::models::User;"
        imports = extractor.extract_imports("test.rs", code, "rust")

        assert len(imports) == 1
        assert imports[0].imported_module == "crate::models::User"
        assert imports[0].is_relative is True

    def test_mod_statement(self, extractor):
        """Test mod statement."""
        code = "mod database;"
        imports = extractor.extract_imports("test.rs", code, "rust")

        assert len(imports) == 1
        assert imports[0].imported_module == "database"
        assert imports[0].import_type == ImportType.MOD
        assert imports[0].is_relative is True

    def test_pub_use(self, extractor):
        """Test pub use statement."""
        code = "pub use crate::error::Error;"
        imports = extractor.extract_imports("test.rs", code, "rust")

        assert len(imports) == 1
        assert imports[0].imported_module == "crate::error::Error"

    def test_super_import(self, extractor):
        """Test super import."""
        code = "use super::models::User;"
        imports = extractor.extract_imports("test.rs", code, "rust")

        assert len(imports) == 1
        assert imports[0].is_relative is True


class TestDependencyMetadata:
    """Test dependency metadata building."""

    def test_build_metadata_empty(self):
        """Test building metadata from empty imports."""
        metadata = build_dependency_metadata([])

        assert metadata["imports"] == []
        assert metadata["dependencies"] == []
        assert metadata["import_count"] == 0

    def test_build_metadata_single(self, extractor):
        """Test building metadata from single import."""
        code = "import os"
        imports = extractor.extract_imports("test.py", code, "python")
        metadata = build_dependency_metadata(imports)

        assert metadata["import_count"] == 1
        assert "os" in metadata["dependencies"]
        assert len(metadata["imports"]) == 1
        assert metadata["imports"][0]["module"] == "os"

    def test_build_metadata_multiple(self, extractor):
        """Test building metadata from multiple imports."""
        code = """
import os
import sys
from pathlib import Path
"""
        imports = extractor.extract_imports("test.py", code, "python")
        metadata = build_dependency_metadata(imports)

        assert metadata["import_count"] == 3
        assert set(metadata["dependencies"]) == {"os", "sys", "pathlib"}
        assert len(metadata["imports"]) == 3

    def test_build_metadata_structure(self, extractor):
        """Test metadata structure."""
        code = "from typing import List, Dict"
        imports = extractor.extract_imports("test.py", code, "python")
        metadata = build_dependency_metadata(imports)

        import_data = metadata["imports"][0]
        assert "module" in import_data
        assert "items" in import_data
        assert "type" in import_data
        assert "line" in import_data
        assert "relative" in import_data
        assert "alias" in import_data


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_unsupported_language(self, extractor):
        """Test extraction for unsupported language."""
        imports = extractor.extract_imports("test.c", "int main() {}", "c")

        assert imports == []

    def test_empty_file(self, extractor):
        """Test extraction from empty file."""
        imports = extractor.extract_imports("test.py", "", "python")

        assert imports == []

    def test_no_imports(self, extractor):
        """Test file with no imports."""
        code = """
def hello():
    print("Hello, World!")
"""
        imports = extractor.extract_imports("test.py", code, "python")

        assert imports == []

    def test_malformed_import(self, extractor):
        """Test malformed import statement."""
        code = "import  # incomplete"
        imports = extractor.extract_imports("test.py", code, "python")

        # Should not crash, just not extract anything
        assert isinstance(imports, list)

    def test_case_insensitive_language(self, extractor):
        """Test language name is case-insensitive."""
        code = "import os"

        imports1 = extractor.extract_imports("test.py", code, "Python")
        imports2 = extractor.extract_imports("test.py", code, "PYTHON")
        imports3 = extractor.extract_imports("test.py", code, "python")

        assert len(imports1) == len(imports2) == len(imports3) == 1
