"""Programming-specific synonyms and query expansion for code search."""

import logging
from typing import Set, Dict
import re

logger = logging.getLogger(__name__)


# Programming term synonyms (bidirectional)
PROGRAMMING_SYNONYMS: Dict[str, Set[str]] = {
    # Authentication & Security
    "auth": {"authentication", "authorize", "login", "signin", "verify"},
    "authentication": {"auth", "authorize", "login", "verify", "credential"},
    "login": {"signin", "auth", "authenticate"},
    "password": {"credentials", "secret", "passphrase"},
    "token": {"jwt", "session", "credential"},
    "permission": {"authorization", "access", "privilege", "rights"},
    # Functions & Methods
    "function": {"method", "procedure", "routine", "func", "def"},
    "method": {"function", "procedure", "routine"},
    "procedure": {"function", "method", "routine"},
    "callback": {"handler", "hook", "listener"},
    # Data Structures
    "array": {"list", "collection", "vector"},
    "list": {"array", "collection", "sequence"},
    "map": {"dict", "dictionary", "hashmap", "table"},
    "dict": {"dictionary", "map", "hashmap", "object"},
    "set": {"collection", "hashset"},
    "queue": {"buffer", "fifo"},
    "stack": {"lifo"},
    "tree": {"hierarchy", "graph"},
    # Database
    "database": {"db", "datastore", "storage", "persistence"},
    "db": {"database", "datastore"},
    "query": {"select", "fetch", "retrieve", "search"},
    "insert": {"create", "add", "store"},
    "update": {"modify", "change", "edit"},
    "delete": {"remove", "destroy", "drop"},
    "table": {"relation", "entity", "collection"},
    "index": {"key", "lookup"},
    # API & Web
    "api": {"endpoint", "service", "interface"},
    "endpoint": {"route", "path", "url", "api"},
    "route": {"endpoint", "path", "handler"},
    "request": {"req", "call", "invocation"},
    "response": {"resp", "reply", "result"},
    "http": {"web", "rest", "api"},
    "rest": {"api", "http", "restful"},
    # Configuration
    "config": {"configuration", "settings", "options", "preferences"},
    "configuration": {"config", "settings", "setup"},
    "settings": {"config", "configuration", "preferences", "options"},
    "environment": {"env", "context", "config"},
    "parameter": {"param", "argument", "option", "setting"},
    "param": {"parameter", "argument", "option"},
    "argument": {"param", "parameter", "arg"},
    # Error Handling
    "error": {"exception", "fault", "failure", "bug"},
    "exception": {"error", "fault", "failure"},
    "exceptions": {"error", "fault", "failure"},  # plural form
    "handle": {"catch", "manage", "process"},
    "catch": {"handle", "trap", "intercept"},
    "throw": {"raise", "emit", "trigger"},
    "log": {"record", "trace", "debug"},
    # Async & Concurrency
    "async": {"asynchronous", "concurrent", "parallel"},
    "asynchronous": {"async", "concurrent", "nonblocking"},
    "sync": {"synchronous", "blocking"},
    "synchronous": {"sync", "blocking", "sequential"},
    "thread": {"worker", "task", "process"},
    "lock": {"mutex", "semaphore", "synchronize"},
    # Classes & OOP
    "class": {"type", "object", "entity", "model"},
    "object": {"instance", "entity"},
    "instance": {"object", "entity"},
    "inherit": {"extend", "derive", "subclass"},
    "interface": {"contract", "protocol", "api"},
    "abstract": {"base", "virtual"},
    # Testing
    "test": {"spec", "check", "verify", "assert"},
    "mock": {"stub", "fake", "dummy"},
    "assert": {"check", "verify", "ensure"},
    # File & I/O
    "file": {"document", "path", "stream"},
    "read": {"load", "fetch", "get", "input"},
    "write": {"save", "store", "output"},
    "parse": {"decode", "deserialize", "read"},
    "serialize": {"encode", "stringify"},
    # Common Actions
    "create": {"make", "build", "generate", "new"},
    "get": {"fetch", "retrieve", "obtain", "read"},
    "set_value": {"update", "assign", "write"},
    "find": {"search", "query", "locate", "lookup"},
    "search": {"find", "query", "lookup", "filter"},
    "filter": {"select", "search", "where"},
    "validate": {"check", "verify", "ensure"},
    "initialize": {"init", "setup", "create"},
    "init": {"initialize", "setup", "create"},
    "start": {"begin", "launch", "run", "execute"},
    "stop": {"end", "terminate", "kill", "shutdown"},
    "run": {"execute", "perform", "invoke", "call"},
    "execute": {"run", "perform", "invoke"},
    # Variables & State
    "variable": {"var", "field", "property", "attribute"},
    "var": {"variable", "field"},
    "field": {"property", "attribute", "member", "variable"},
    "property": {"field", "attribute", "member"},
    "state": {"status", "condition", "context"},
    "value": {"data", "content", "result"},
    # Networking
    "client": {"consumer", "requester"},
    "server": {"service", "provider", "backend"},
    "socket": {"connection", "stream"},
    "port": {"endpoint", "address"},
    "host": {"server", "domain", "address"},
    # Security
    "encrypt": {"encode", "cipher", "secure"},
    "decrypt": {"decode", "decipher"},
    "hash": {"digest", "checksum"},
    "secure": {"safe", "protected", "authenticated"},
    # Common Prefixes/Patterns
    "user": {"account", "profile", "customer"},
    "session": {"context", "state", "connection"},
    "cache": {"buffer", "storage", "temp"},
    "temp": {"temporary", "cache", "scratch"},
    "util": {"utility", "helper", "tool"},
    "helper": {"utility", "util", "tool"},
}


# Code context patterns - domain-specific expansions
CODE_CONTEXT_PATTERNS: Dict[str, Set[str]] = {
    # When user searches for "auth", add these related concepts
    "auth": {
        "user",
        "login",
        "password",
        "token",
        "session",
        "permission",
        "role",
        "access",
    },
    "authentication": {
        "user",
        "login",
        "password",
        "credentials",
        "token",
        "session",
        "verify",
    },
    "authorization": {"permission", "access", "role", "rights", "privilege", "acl"},
    # Database operations
    "database": {"connection", "query", "transaction", "schema", "table", "index"},
    "sql": {"query", "select", "insert", "update", "delete", "join", "where"},
    "orm": {"model", "entity", "mapping", "relation", "query"},
    # API patterns
    "api": {"endpoint", "route", "request", "response", "http", "rest", "json"},
    "rest": {"get", "post", "put", "delete", "endpoint", "resource"},
    "graphql": {"query", "mutation", "schema", "resolver", "type"},
    # Frontend
    "react": {"component", "hook", "state", "props", "jsx"},
    "vue": {"component", "template", "reactive", "computed"},
    "angular": {"component", "directive", "service", "module"},
    # Testing
    "test": {"spec", "assert", "mock", "fixture", "setup", "teardown"},
    "unittest": {"assert", "test", "case", "suite", "fixture"},
    "integration": {"test", "e2e", "end to end"},
    # Error handling
    "error": {"exception", "try", "catch", "finally", "throw", "handle"},
    "exception": {"try", "catch", "throw", "error", "fault"},
    "exceptions": {"try", "catch", "throw", "error", "fault"},  # plural form
    # Async patterns
    "async": {"await", "promise", "future", "callback", "concurrent"},
    "promise": {"then", "catch", "async", "await", "resolve", "reject"},
    # Configuration
    "config": {"environment", "settings", "yaml", "json", "toml", "env"},
    "environment": {"config", "env", "variable", "settings"},
}


# Language-specific patterns
LANGUAGE_PATTERNS: Dict[str, Set[str]] = {
    "python": {"def", "class", "import", "from", "self", "init", "lambda"},
    "javascript": {"function", "const", "let", "var", "arrow", "promise", "async"},
    "typescript": {"interface", "type", "generic", "enum", "namespace"},
    "java": {"class", "interface", "extends", "implements", "public", "private"},
    "go": {"func", "struct", "interface", "goroutine", "channel"},
    "rust": {"fn", "struct", "impl", "trait", "mod", "pub"},
}


def expand_with_synonyms(query: str, max_synonyms: int = 3) -> str:
    """
    Expand query with programming synonyms.

    Args:
        query: Original query
        max_synonyms: Maximum synonyms to add per term

    Returns:
        Expanded query with synonyms
    """
    # Extract words from query
    words = re.findall(r"\w+", query.lower())

    # Collect synonyms
    synonyms_to_add = []

    for word in words:
        if word in PROGRAMMING_SYNONYMS:
            # Get synonyms for this word
            word_synonyms = PROGRAMMING_SYNONYMS[word]

            # Add up to max_synonyms
            for synonym in sorted(word_synonyms)[:max_synonyms]:
                if synonym not in words and synonym not in synonyms_to_add:
                    synonyms_to_add.append(synonym)

    # Build expanded query
    if synonyms_to_add:
        expansion = " ".join(synonyms_to_add)
        return f"{query} {expansion}"

    return query


def expand_with_code_context(query: str, max_context_terms: int = 5) -> str:
    """
    Expand query with code context patterns.

    Args:
        query: Original query
        max_context_terms: Maximum context terms to add

    Returns:
        Expanded query with code context
    """
    # Extract words from query
    words = re.findall(r"\w+", query.lower())

    # Collect context terms
    context_terms = set()

    for word in words:
        if word in CODE_CONTEXT_PATTERNS:
            # Get context terms
            word_context = CODE_CONTEXT_PATTERNS[word]

            # Add terms not already in query
            for term in word_context:
                if term not in words:
                    context_terms.add(term)

    # Limit to max_context_terms
    if context_terms:
        terms_to_add = sorted(context_terms)[:max_context_terms]
        expansion = " ".join(terms_to_add)
        return f"{query} {expansion}"

    return query


def expand_query_full(
    query: str,
    enable_synonyms: bool = True,
    enable_context: bool = True,
    max_synonyms: int = 2,
    max_context_terms: int = 3,
) -> str:
    """
    Full query expansion with synonyms and code context.

    Args:
        query: Original query
        enable_synonyms: Whether to add synonyms
        enable_context: Whether to add code context
        max_synonyms: Max synonyms per term
        max_context_terms: Max context terms total

    Returns:
        Fully expanded query
    """
    expanded = query

    if enable_synonyms:
        expanded = expand_with_synonyms(expanded, max_synonyms)

    if enable_context:
        expanded = expand_with_code_context(expanded, max_context_terms)

    logger.debug(f"Query expansion: '{query}' -> '{expanded}'")

    return expanded


def get_synonyms(term: str) -> Set[str]:
    """
    Get all synonyms for a given term.

    Args:
        term: Programming term

    Returns:
        Set of synonyms
    """
    term_lower = term.lower()
    return PROGRAMMING_SYNONYMS.get(term_lower, set())


def get_code_context(term: str) -> Set[str]:
    """
    Get code context terms for a given term.

    Args:
        term: Programming term

    Returns:
        Set of context terms
    """
    term_lower = term.lower()
    return CODE_CONTEXT_PATTERNS.get(term_lower, set())
