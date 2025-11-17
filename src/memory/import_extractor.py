"""Import and dependency extraction from source code."""

import re
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ImportType(str, Enum):
    """Types of import statements."""
    IMPORT = "import"
    FROM_IMPORT = "from_import"
    REQUIRE = "require"
    DYNAMIC_IMPORT = "dynamic_import"
    USE = "use"
    MOD = "mod"


@dataclass
class ImportInfo:
    """Represents an import/dependency statement."""
    source_file: str  # File containing the import
    imported_module: str  # Module/file being imported
    imported_items: List[str]  # Specific items imported (e.g., ["Path", "Path"])
    import_type: ImportType
    line_number: int
    is_relative: bool  # Relative vs absolute import
    alias: Optional[str] = None  # Import alias if any
    raw_statement: str = ""  # Original import statement


class ImportExtractor:
    """Extract import statements from source code across multiple languages."""

    def __init__(self):
        """Initialize the import extractor."""
        self.extractors = {
            "python": self._extract_python_imports,
            "javascript": self._extract_javascript_imports,
            "typescript": self._extract_javascript_imports,  # Same as JS
            "java": self._extract_java_imports,
            "go": self._extract_go_imports,
            "rust": self._extract_rust_imports,
        }

    def extract_imports(
        self,
        file_path: str,
        source_code: str,
        language: str
    ) -> List[ImportInfo]:
        """
        Extract all imports from source code.

        Args:
            file_path: Path to the source file
            source_code: Source code content
            language: Programming language

        Returns:
            List of ImportInfo objects
        """
        language_lower = language.lower()
        extractor = self.extractors.get(language_lower)

        if not extractor:
            logger.debug(f"No import extractor for language: {language}")
            return []

        try:
            return extractor(file_path, source_code)
        except Exception as e:
            logger.warning(f"Failed to extract imports from {file_path}: {e}")
            return []

    def _extract_python_imports(
        self,
        file_path: str,
        source_code: str
    ) -> List[ImportInfo]:
        """
        Extract Python imports.

        Handles:
        - import module
        - import module as alias
        - from module import item
        - from module import item as alias
        - from . import relative
        - from ..parent import something
        """
        imports = []
        lines = source_code.split('\n')

        # Pattern 1: import module [as alias]
        import_pattern = re.compile(
            r'^\s*import\s+([a-zA-Z0-9_.]+)(?:\s+as\s+([a-zA-Z0-9_]+))?'
        )

        # Pattern 2: from module import items
        from_import_pattern = re.compile(
            r'^\s*from\s+(\.{0,2}[a-zA-Z0-9_.]*)\s+import\s+(.+)'
        )

        for line_num, line in enumerate(lines, start=1):
            # Skip comments
            if line.strip().startswith('#'):
                continue

            # Match: import module [as alias]
            match = import_pattern.match(line)
            if match:
                module = match.group(1)
                alias = match.group(2)
                imports.append(ImportInfo(
                    source_file=file_path,
                    imported_module=module,
                    imported_items=[],
                    import_type=ImportType.IMPORT,
                    line_number=line_num,
                    is_relative=module.startswith('.'),
                    alias=alias,
                    raw_statement=line.strip()
                ))
                continue

            # Match: from module import items
            match = from_import_pattern.match(line)
            if match:
                module = match.group(1)
                items_str = match.group(2)

                # Parse imported items
                items = []
                if items_str.strip() == '*':
                    items = ['*']
                else:
                    # Handle: from x import a, b as c, d
                    for item in items_str.split(','):
                        item = item.strip()
                        # Remove 'as alias' part
                        if ' as ' in item:
                            item = item.split(' as ')[0].strip()
                        if item:
                            items.append(item)

                imports.append(ImportInfo(
                    source_file=file_path,
                    imported_module=module,
                    imported_items=items,
                    import_type=ImportType.FROM_IMPORT,
                    line_number=line_num,
                    is_relative=module.startswith('.'),
                    raw_statement=line.strip()
                ))

        return imports

    def _extract_javascript_imports(
        self,
        file_path: str,
        source_code: str
    ) -> List[ImportInfo]:
        """
        Extract JavaScript/TypeScript imports.

        Handles:
        - import { x, y } from 'module'
        - import * as name from 'module'
        - import defaultExport from 'module'
        - const x = require('module')
        - import('module') - dynamic import
        """
        imports = []
        lines = source_code.split('\n')

        # Pattern 1: import ... from 'module'
        # Handles: import {x} from 'y', import * as x from 'y', import x from 'y'
        import_pattern = re.compile(
            r'^\s*import\s+(?:((?:{.*?}|\*\s+as\s+\w+|[a-zA-Z0-9_$]+))\s+)?from\s+["\'](.+?)["\']'
        )

        # Pattern 2: const x = require('module')
        require_pattern = re.compile(
            r'^\s*(?:const|let|var)\s+.*?=\s*require\(["\'](.+?)["\']\)'
        )

        # Pattern 3: import('module') - dynamic
        dynamic_import_pattern = re.compile(
            r'import\(["\'](.+?)["\']\)'
        )

        for line_num, line in enumerate(lines, start=1):
            # Skip comments
            if line.strip().startswith('//'):
                continue

            # Match: import ... from 'module'
            match = import_pattern.match(line)
            if match:
                items_str = match.group(1) or ''
                module = match.group(2)

                # Parse imported items
                items = []
                if items_str:
                    if items_str.startswith('{') and items_str.endswith('}'):
                        # Named imports: { x, y }
                        items_str = items_str[1:-1]
                        for item in items_str.split(','):
                            item = item.strip()
                            if ' as ' in item:
                                item = item.split(' as ')[0].strip()
                            if item:
                                items.append(item)
                    elif '*' in items_str:
                        # Namespace import: * as name
                        items = ['*']
                    else:
                        # Default import
                        items = [items_str.strip()]

                imports.append(ImportInfo(
                    source_file=file_path,
                    imported_module=module,
                    imported_items=items,
                    import_type=ImportType.IMPORT,
                    line_number=line_num,
                    is_relative=module.startswith('.'),
                    raw_statement=line.strip()
                ))
                continue

            # Match: require('module')
            match = require_pattern.match(line)
            if match:
                module = match.group(1)
                imports.append(ImportInfo(
                    source_file=file_path,
                    imported_module=module,
                    imported_items=[],
                    import_type=ImportType.REQUIRE,
                    line_number=line_num,
                    is_relative=module.startswith('.'),
                    raw_statement=line.strip()
                ))
                continue

            # Match: dynamic import (can appear anywhere in line)
            for match in dynamic_import_pattern.finditer(line):
                module = match.group(1)
                imports.append(ImportInfo(
                    source_file=file_path,
                    imported_module=module,
                    imported_items=[],
                    import_type=ImportType.DYNAMIC_IMPORT,
                    line_number=line_num,
                    is_relative=module.startswith('.'),
                    raw_statement=match.group(0)
                ))

        return imports

    def _extract_java_imports(
        self,
        file_path: str,
        source_code: str
    ) -> List[ImportInfo]:
        """
        Extract Java imports.

        Handles:
        - import package.Class;
        - import static package.Class.method;
        - import package.*;
        """
        imports = []
        lines = source_code.split('\n')

        # Pattern: import [static] package.Class;
        import_pattern = re.compile(
            r'^\s*import\s+(?:static\s+)?([a-zA-Z0-9_.]+(?:\.\*)?);\s*$'
        )

        for line_num, line in enumerate(lines, start=1):
            match = import_pattern.match(line)
            if match:
                full_path = match.group(1)

                # Extract class/items from module path
                items = []
                module = full_path

                if full_path.endswith('.*'):
                    items = ['*']
                    module = full_path[:-2]  # Remove .*
                else:
                    # Last part is the class name, rest is the package
                    parts = full_path.split('.')
                    if len(parts) > 1:
                        items = [parts[-1]]
                        module = '.'.join(parts[:-1])
                    else:
                        # Single name (unusual but possible)
                        items = [parts[0]]
                        module = ''

                imports.append(ImportInfo(
                    source_file=file_path,
                    imported_module=module,
                    imported_items=items,
                    import_type=ImportType.IMPORT,
                    line_number=line_num,
                    is_relative=False,  # Java imports are always absolute
                    raw_statement=line.strip()
                ))

        return imports

    def _extract_go_imports(
        self,
        file_path: str,
        source_code: str
    ) -> List[ImportInfo]:
        """
        Extract Go imports.

        Handles:
        - import "package"
        - import ( "pkg1" "pkg2" )
        - import alias "package"
        """
        imports = []
        lines = source_code.split('\n')

        # Single import pattern
        single_import_pattern = re.compile(
            r'^\s*import\s+(?:([a-zA-Z0-9_]+)\s+)?"(.+?)"\s*$'
        )

        # Multi-import block
        in_import_block = False
        import_block_pattern = re.compile(r'^\s*import\s+\(\s*$')
        import_block_end = re.compile(r'^\s*\)\s*$')
        import_item_pattern = re.compile(
            r'^\s*(?:([a-zA-Z0-9_]+)\s+)?"(.+?)"\s*$'
        )

        for line_num, line in enumerate(lines, start=1):
            # Check for import block start
            if import_block_pattern.match(line):
                in_import_block = True
                continue

            # Check for import block end
            if in_import_block and import_block_end.match(line):
                in_import_block = False
                continue

            # Parse import in block
            if in_import_block:
                match = import_item_pattern.match(line)
                if match:
                    alias = match.group(1)
                    module = match.group(2)
                    imports.append(ImportInfo(
                        source_file=file_path,
                        imported_module=module,
                        imported_items=[],
                        import_type=ImportType.IMPORT,
                        line_number=line_num,
                        is_relative=module.startswith('.'),
                        alias=alias,
                        raw_statement=line.strip()
                    ))
                continue

            # Parse single import
            match = single_import_pattern.match(line)
            if match:
                alias = match.group(1)
                module = match.group(2)
                imports.append(ImportInfo(
                    source_file=file_path,
                    imported_module=module,
                    imported_items=[],
                    import_type=ImportType.IMPORT,
                    line_number=line_num,
                    is_relative=module.startswith('.'),
                    alias=alias,
                    raw_statement=line.strip()
                ))

        return imports

    def _extract_rust_imports(
        self,
        file_path: str,
        source_code: str
    ) -> List[ImportInfo]:
        """
        Extract Rust imports.

        Handles:
        - use std::collections::HashMap;
        - use crate::module::{Type1, Type2};
        - mod module_name;
        """
        imports = []
        lines = source_code.split('\n')

        # Pattern 1: use path::to::item;
        use_pattern = re.compile(
            r'^\s*(?:pub\s+)?use\s+([a-zA-Z0-9_:]+)(?:::\{(.+?)\})?(?:::\*)?;'
        )

        # Pattern 2: mod module;
        mod_pattern = re.compile(
            r'^\s*(?:pub\s+)?mod\s+([a-zA-Z0-9_]+)\s*;'
        )

        for line_num, line in enumerate(lines, start=1):
            # Match: use path;
            match = use_pattern.match(line)
            if match:
                module = match.group(1)
                items_str = match.group(2)

                items = []
                if items_str:
                    # use path::{item1, item2}
                    for item in items_str.split(','):
                        item = item.strip()
                        if ' as ' in item:
                            item = item.split(' as ')[0].strip()
                        if item:
                            items.append(item)
                elif '::*' in line:
                    items = ['*']
                else:
                    # Last part is the item
                    parts = module.split('::')
                    if parts:
                        items = [parts[-1]]

                imports.append(ImportInfo(
                    source_file=file_path,
                    imported_module=module,
                    imported_items=items,
                    import_type=ImportType.USE,
                    line_number=line_num,
                    is_relative=module.startswith('crate::') or module.startswith('super::'),
                    raw_statement=line.strip()
                ))
                continue

            # Match: mod module;
            match = mod_pattern.match(line)
            if match:
                module = match.group(1)
                imports.append(ImportInfo(
                    source_file=file_path,
                    imported_module=module,
                    imported_items=[],
                    import_type=ImportType.MOD,
                    line_number=line_num,
                    is_relative=True,  # mod is always relative to current crate
                    raw_statement=line.strip()
                ))

        return imports


def build_dependency_metadata(imports: List[ImportInfo]) -> Dict[str, Any]:
    """
    Build dependency metadata from extracted imports.

    Args:
        imports: List of ImportInfo objects

    Returns:
        Dictionary with dependency metadata
    """
    if not imports:
        return {
            "imports": [],
            "dependencies": [],
            "import_count": 0
        }

    # Collect unique dependencies (modules)
    dependencies = set()
    import_data = []

    for imp in imports:
        dependencies.add(imp.imported_module)
        import_data.append({
            "module": imp.imported_module,
            "items": imp.imported_items,
            "type": imp.import_type.value,
            "line": imp.line_number,
            "relative": imp.is_relative,
            "alias": imp.alias
        })

    return {
        "imports": import_data,
        "dependencies": sorted(list(dependencies)),
        "import_count": len(imports)
    }
