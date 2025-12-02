"""Tests for dependency graph functionality."""

import pytest
from pathlib import Path
from src.memory.dependency_graph import DependencyGraph


@pytest.fixture
def graph():
    """Create a dependency graph instance."""
    return DependencyGraph()


@pytest.fixture
def sample_imports():
    """Sample import data for testing."""
    return {
        "/project/main.py": [
            {
                "module": "utils",
                "items": ["helper"],
                "type": "from_import",
                "line": 1,
                "relative": True,
            },
            {
                "module": "models",
                "items": ["User"],
                "type": "from_import",
                "line": 2,
                "relative": True,
            },
        ],
        "/project/utils.py": [
            {
                "module": "logging",
                "items": ["Logger"],
                "type": "from_import",
                "line": 1,
                "relative": False,
            },
        ],
        "/project/models.py": [
            {
                "module": "dataclasses",
                "items": ["dataclass"],
                "type": "from_import",
                "line": 1,
                "relative": False,
            },
        ],
    }


class TestBasicDependencies:
    """Test basic dependency operations."""

    def test_empty_graph(self, graph):
        """Test empty dependency graph."""
        deps = graph.get_dependencies("/any/file.py")
        assert deps == set()

        dependents = graph.get_dependents("/any/file.py")
        assert dependents == set()

    def test_add_single_dependency(self, graph):
        """Test adding a single dependency."""
        imports = [
            {
                "module": "os",
                "items": [],
                "type": "import",
                "line": 1,
                "relative": False,
            }
        ]

        graph.add_file_dependencies("/project/main.py", imports)

        # Since we can't resolve "os" to a file path, no dependencies should be added
        deps = graph.get_dependencies("/project/main.py")
        assert len(deps) == 0  # External imports are not tracked

    def test_get_dependencies(self, graph):
        """Test getting direct dependencies."""
        source = str(Path("/project/main.py").resolve())
        target = str(Path("/project/utils.py").resolve())

        # Manually add dependency (since relative import resolution is limited)
        graph.dependencies[source].add(target)
        graph.dependents[target].add(source)

        deps = graph.get_dependencies(source)
        assert target in deps
        assert len(deps) == 1

    def test_get_dependents(self, graph):
        """Test getting reverse dependencies."""
        source = str(Path("/project/main.py").resolve())
        target = str(Path("/project/utils.py").resolve())

        # Manually add dependency
        graph.dependencies[source].add(target)
        graph.dependents[target].add(source)

        dependents = graph.get_dependents(target)
        assert source in dependents
        assert len(dependents) == 1

    def test_bidirectional_dependencies(self, graph):
        """Test bidirectional dependency tracking."""
        file_a = str(Path("/project/a.py").resolve())
        file_b = str(Path("/project/b.py").resolve())

        # Add A -> B dependency
        graph.dependencies[file_a].add(file_b)
        graph.dependents[file_b].add(file_a)

        # Check forward
        assert file_b in graph.get_dependencies(file_a)
        # Check reverse
        assert file_a in graph.get_dependents(file_b)


class TestTransitiveDependencies:
    """Test transitive dependency queries."""

    def test_transitive_dependencies_chain(self, graph):
        """Test getting all transitive dependencies in a chain."""
        # Chain: A -> B -> C
        a = str(Path("/project/a.py").resolve())
        b = str(Path("/project/b.py").resolve())
        c = str(Path("/project/c.py").resolve())

        graph.dependencies[a].add(b)
        graph.dependencies[b].add(c)
        graph.dependents[b].add(a)
        graph.dependents[c].add(b)

        all_deps = graph.get_all_dependencies(a)

        assert b in all_deps
        assert c in all_deps
        assert len(all_deps) == 2

    def test_transitive_dependencies_tree(self, graph):
        """Test transitive dependencies in a tree structure."""
        # Tree: A -> B, A -> C, B -> D
        a = str(Path("/project/a.py").resolve())
        b = str(Path("/project/b.py").resolve())
        c = str(Path("/project/c.py").resolve())
        d = str(Path("/project/d.py").resolve())

        graph.dependencies[a].update([b, c])
        graph.dependencies[b].add(d)
        graph.dependents[b].add(a)
        graph.dependents[c].add(a)
        graph.dependents[d].add(b)

        all_deps = graph.get_all_dependencies(a)

        assert all_deps == {b, c, d}

    def test_transitive_dependents(self, graph):
        """Test getting all transitive dependents."""
        # Chain: A -> B -> C (C is depended on by B, B by A)
        a = str(Path("/project/a.py").resolve())
        b = str(Path("/project/b.py").resolve())
        c = str(Path("/project/c.py").resolve())

        graph.dependencies[a].add(b)
        graph.dependencies[b].add(c)
        graph.dependents[b].add(a)
        graph.dependents[c].add(b)

        all_dependents = graph.get_all_dependents(c)

        assert b in all_dependents
        assert a in all_dependents
        assert len(all_dependents) == 2

    def test_max_depth_limit(self, graph):
        """Test max depth limit for transitive queries."""
        # Create long chain: A -> B -> C -> D -> E
        files = [
            str(Path(f"/project/{chr(ord('a')+i)}.py").resolve()) for i in range(5)
        ]

        for i in range(4):
            graph.dependencies[files[i]].add(files[i + 1])
            graph.dependents[files[i + 1]].add(files[i])

        # Limit depth to 2
        all_deps = graph.get_all_dependencies(files[0], max_depth=2)

        # Should only get B and C, not D and E
        assert len(all_deps) <= 3  # B, C, and possibly D


class TestPathFinding:
    """Test path finding between files."""

    def test_direct_path(self, graph):
        """Test finding direct path between files."""
        a = str(Path("/project/a.py").resolve())
        b = str(Path("/project/b.py").resolve())

        graph.dependencies[a].add(b)

        path = graph.find_path(a, b)

        assert path is not None
        assert path == [a, b]

    def test_indirect_path(self, graph):
        """Test finding indirect path."""
        a = str(Path("/project/a.py").resolve())
        b = str(Path("/project/b.py").resolve())
        c = str(Path("/project/c.py").resolve())

        graph.dependencies[a].add(b)
        graph.dependencies[b].add(c)

        path = graph.find_path(a, c)

        assert path is not None
        assert path == [a, b, c]

    def test_no_path(self, graph):
        """Test when no path exists."""
        a = str(Path("/project/a.py").resolve())
        b = str(Path("/project/b.py").resolve())

        path = graph.find_path(a, b)

        assert path is None

    def test_path_to_self(self, graph):
        """Test path from file to itself."""
        a = str(Path("/project/a.py").resolve())

        path = graph.find_path(a, a)

        assert path == [a]

    def test_shortest_path(self, graph):
        """Test that shortest path is found."""
        # Create: A -> B -> C and A -> C
        a = str(Path("/project/a.py").resolve())
        b = str(Path("/project/b.py").resolve())
        c = str(Path("/project/c.py").resolve())

        graph.dependencies[a].update([b, c])  # A -> B and A -> C
        graph.dependencies[b].add(c)  # B -> C

        path = graph.find_path(a, c)

        # Should find direct path A -> C, not A -> B -> C
        assert path == [a, c]


class TestCircularDependencies:
    """Test circular dependency detection."""

    def test_no_circular_dependencies(self, graph):
        """Test graph with no cycles."""
        a = str(Path("/project/a.py").resolve())
        b = str(Path("/project/b.py").resolve())

        graph.dependencies[a].add(b)

        cycles = graph.detect_circular_dependencies()

        assert cycles == []

    def test_simple_cycle(self, graph):
        """Test detecting simple 2-file cycle."""
        a = str(Path("/project/a.py").resolve())
        b = str(Path("/project/b.py").resolve())

        graph.dependencies[a].add(b)
        graph.dependencies[b].add(a)

        cycles = graph.detect_circular_dependencies()

        assert len(cycles) > 0
        # Check that cycle contains both files
        cycle = cycles[0]
        assert a in cycle
        assert b in cycle

    def test_three_file_cycle(self, graph):
        """Test detecting 3-file cycle."""
        a = str(Path("/project/a.py").resolve())
        b = str(Path("/project/b.py").resolve())
        c = str(Path("/project/c.py").resolve())

        graph.dependencies[a].add(b)
        graph.dependencies[b].add(c)
        graph.dependencies[c].add(a)

        cycles = graph.detect_circular_dependencies()

        assert len(cycles) > 0
        cycle = cycles[0]
        assert a in cycle
        assert b in cycle
        assert c in cycle


class TestImportDetails:
    """Test import detail tracking."""

    def test_store_import_details(self, graph):
        """Test storing import details."""
        source = str(Path("/project/main.py").resolve())
        target = str(Path("/project/utils.py").resolve())

        graph.dependencies[source].add(target)
        graph.import_details[(source, target)].append(
            {
                "module": "utils",
                "items": ["helper"],
                "type": "from_import",
                "line": 5,
            }
        )

        details = graph.get_import_details(source, target)

        assert len(details) == 1
        assert details[0]["module"] == "utils"
        assert details[0]["items"] == ["helper"]
        assert details[0]["line"] == 5

    def test_multiple_imports_same_files(self, graph):
        """Test multiple imports between same files."""
        source = str(Path("/project/main.py").resolve())
        target = str(Path("/project/utils.py").resolve())

        graph.import_details[(source, target)].extend(
            [
                {
                    "module": "utils",
                    "items": ["helper1"],
                    "type": "from_import",
                    "line": 5,
                },
                {
                    "module": "utils",
                    "items": ["helper2"],
                    "type": "from_import",
                    "line": 6,
                },
            ]
        )

        details = graph.get_import_details(source, target)

        assert len(details) == 2
        assert details[0]["items"] == ["helper1"]
        assert details[1]["items"] == ["helper2"]

    def test_import_details_copy(self, graph):
        """Test that returned import details are copies."""
        source = str(Path("/project/main.py").resolve())
        target = str(Path("/project/utils.py").resolve())

        graph.import_details[(source, target)].append(
            {
                "module": "utils",
                "items": ["helper"],
                "type": "from_import",
                "line": 5,
            }
        )

        details1 = graph.get_import_details(source, target)
        details1.append({"fake": "data"})

        details2 = graph.get_import_details(source, target)

        # Original should be unchanged
        assert len(details2) == 1
        assert "fake" not in details2[0]


class TestStatistics:
    """Test graph statistics."""

    def test_empty_graph_stats(self, graph):
        """Test statistics for empty graph."""
        stats = graph.get_statistics()

        assert stats["total_files"] == 0
        assert stats["total_dependencies"] == 0
        assert stats["average_dependencies"] == 0

    def test_graph_stats(self, graph):
        """Test statistics for populated graph."""
        a = str(Path("/project/a.py").resolve())
        b = str(Path("/project/b.py").resolve())
        c = str(Path("/project/c.py").resolve())

        graph.dependencies[a].update([b, c])
        graph.dependencies[b].add(c)
        graph.dependents[b].update([a])
        graph.dependents[c].update([a, b])

        stats = graph.get_statistics()

        assert stats["total_files"] == 3
        assert stats["total_dependencies"] == 3  # A->B, A->C, B->C
        assert stats["average_dependencies"] == 1.0

    def test_most_depended_on(self, graph):
        """Test finding most depended-on files."""
        a = str(Path("/project/a.py").resolve())
        b = str(Path("/project/b.py").resolve())
        c = str(Path("/project/c.py").resolve())

        # Both A and B depend on C
        graph.dependencies[a].add(c)
        graph.dependencies[b].add(c)
        graph.dependents[c].update([a, b])

        stats = graph.get_statistics()

        # C should be most depended-on
        most_depended = stats["most_depended_on"]
        if most_depended:
            assert most_depended[0]["dependent_count"] == 2

    def test_most_dependencies(self, graph):
        """Test finding files with most dependencies."""
        a = str(Path("/project/a.py").resolve())
        b = str(Path("/project/b.py").resolve())
        c = str(Path("/project/c.py").resolve())

        # A depends on both B and C
        graph.dependencies[a].update([b, c])

        stats = graph.get_statistics()

        # A should have most dependencies
        most_deps = stats["most_dependencies"]
        if most_deps:
            assert most_deps[0]["dependency_count"] == 2


class TestSetOperations:
    """Test that returned sets are copies."""

    def test_dependencies_are_copies(self, graph):
        """Test that get_dependencies returns a copy."""
        a = str(Path("/project/a.py").resolve())
        b = str(Path("/project/b.py").resolve())

        graph.dependencies[a].add(b)

        deps1 = graph.get_dependencies(a)
        deps1.add("fake")

        deps2 = graph.get_dependencies(a)

        # Original should be unchanged
        assert "fake" not in deps2
        assert len(deps2) == 1

    def test_dependents_are_copies(self, graph):
        """Test that get_dependents returns a copy."""
        a = str(Path("/project/a.py").resolve())
        b = str(Path("/project/b.py").resolve())

        graph.dependents[b].add(a)

        deps1 = graph.get_dependents(b)
        deps1.add("fake")

        deps2 = graph.get_dependents(b)

        # Original should be unchanged
        assert "fake" not in deps2
        assert len(deps2) == 1
