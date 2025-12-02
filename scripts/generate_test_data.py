#!/usr/bin/env python3
"""Generate large test databases for performance testing."""

import asyncio
import sys
import time
from pathlib import Path
import random
from datetime import datetime, timedelta, UTC

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import ServerConfig
from src.core.server import MemoryRAGServer
from src.core.models import MemoryCategory, ContextLevel


# Sample content templates
FACT_TEMPLATES = [
    "The {technology} framework uses {pattern} for {purpose}.",
    "In {language}, {feature} is implemented using {method}.",
    "The {component} system handles {operation} through {mechanism}.",
    "When working with {tool}, it's important to {action} for {reason}.",
    "The {library} provides {functionality} via {interface}.",
]

PREFERENCE_TEMPLATES = [
    "User prefers {choice1} over {choice2} for {context}.",
    "Preferred {style} when working on {project_type} projects.",
    "Always use {tool} for {task} instead of {alternative}.",
    "Code style preference: {detail} in {language}.",
    "Testing approach: {method} for {scenario}.",
]

PROJECT_TEMPLATES = [
    "The {project} uses {architecture} with {database}.",
    "API endpoints in {project} follow {pattern} convention.",
    "{module} handles {responsibility} in the {project}.",
    "Deployment process for {project}: {steps}.",
    "Configuration for {project} is stored in {location}.",
]

SESSION_TEMPLATES = [
    "Currently working on {task} in {file}.",
    "Last {action} was at {location}.",
    "Next step: {next_task} after {current_task}.",
    "Debugging {issue} in {component}.",
    "Implementing {feature} using {approach}.",
]

# Sample values for templates
TECHNOLOGIES = ["React", "Vue", "Angular", "Django", "FastAPI", "Express"]
LANGUAGES = ["Python", "JavaScript", "TypeScript", "Go", "Rust", "Java"]
PATTERNS = ["MVC", "MVVM", "Redux", "Observer", "Factory", "Singleton"]
TOOLS = ["Docker", "Kubernetes", "Git", "npm", "pip", "cargo"]
PROJECTS = ["api-server", "web-app", "mobile-app", "cli-tool", "library"]


def generate_random_content(category: MemoryCategory) -> str:
    """Generate random content based on category."""
    if category == MemoryCategory.FACT:
        template = random.choice(FACT_TEMPLATES)
        return template.format(
            technology=random.choice(TECHNOLOGIES),
            pattern=random.choice(PATTERNS),
            purpose=random.choice(["routing", "state management", "data flow"]),
            language=random.choice(LANGUAGES),
            feature=random.choice(["async/await", "decorators", "generics"]),
            method=random.choice(["closures", "promises", "channels"]),
            component=random.choice(["auth", "cache", "queue"]),
            operation=random.choice(["requests", "events", "data"]),
            mechanism=random.choice(["middleware", "interceptors", "handlers"]),
            tool=random.choice(TOOLS),
            action=random.choice(["configure", "optimize", "test"]),
            reason=random.choice(["performance", "security", "maintainability"]),
            library=random.choice(["axios", "lodash", "pandas"]),
            functionality=random.choice(
                ["HTTP requests", "data manipulation", "parsing"]
            ),
            interface=random.choice(["REST API", "CLI", "SDK"]),
        )
    elif category == MemoryCategory.PREFERENCE:
        template = random.choice(PREFERENCE_TEMPLATES)
        return template.format(
            choice1=random.choice(["tabs", "spaces", "semicolons"]),
            choice2=random.choice(["spaces", "tabs", "no semicolons"]),
            context=random.choice(["Python", "JavaScript", "TypeScript"]),
            style=random.choice(["functional", "OOP", "imperative"]),
            project_type=random.choice(["web", "mobile", "backend"]),
            tool=random.choice(TOOLS),
            task=random.choice(["testing", "deployment", "debugging"]),
            alternative=random.choice(["manual process", "GUI tools", "scripts"]),
            detail=random.choice(
                ["4 spaces indentation", "camelCase naming", "80 char limit"]
            ),
            language=random.choice(LANGUAGES),
            method=random.choice(
                ["unit tests first", "integration tests", "E2E tests"]
            ),
            scenario=random.choice(["API changes", "refactoring", "new features"]),
        )
    elif category == MemoryCategory.PROJECT_CONTEXT:
        template = random.choice(PROJECT_TEMPLATES)
        return template.format(
            project=random.choice(PROJECTS),
            architecture=random.choice(["microservices", "monolith", "serverless"]),
            database=random.choice(["PostgreSQL", "MongoDB", "Redis"]),
            pattern=random.choice(["RESTful", "GraphQL", "gRPC"]),
            module=random.choice(["auth module", "user service", "payment gateway"]),
            responsibility=random.choice(
                ["authentication", "data validation", "caching"]
            ),
            steps=random.choice(
                ["CI/CD pipeline", "manual deployment", "automated scripts"]
            ),
            location=random.choice(
                [".env file", "config.yaml", "environment variables"]
            ),
        )
    else:  # SESSION_STATE
        template = random.choice(SESSION_TEMPLATES)
        return template.format(
            task=random.choice(["refactoring", "bug fix", "feature implementation"]),
            file=random.choice(["auth.py", "server.js", "main.go"]),
            action=random.choice(["edit", "test", "commit"]),
            location=random.choice(["line 42", "function foo()", "class Bar"]),
            next_task=random.choice(["testing", "documentation", "code review"]),
            current_task=random.choice(["implementation", "debugging", "refactoring"]),
            issue=random.choice(["null pointer", "race condition", "memory leak"]),
            component=random.choice(["database layer", "API handler", "frontend"]),
            feature=random.choice(
                ["user authentication", "data export", "real-time updates"]
            ),
            approach=random.choice(["TDD", "bottom-up", "top-down"]),
        )


async def generate_test_database(
    size: int,
    output_name: str = "performance_test",
    category_distribution: dict = None,
) -> None:
    """
    Generate a test database with specified number of memories.

    Args:
        size: Number of memories to generate
        output_name: Name for the test database
        category_distribution: Dict with category percentages (default: balanced)
    """
    if category_distribution is None:
        category_distribution = {
            MemoryCategory.FACT: 0.40,
            MemoryCategory.PREFERENCE: 0.30,
            MemoryCategory.PROJECT_CONTEXT: 0.20,
            MemoryCategory.SESSION_STATE: 0.10,
        }

    print(f"\n{'='*70}")
    print(f"Generating Test Database: {output_name}")
    print(f"Target Size: {size:,} memories")
    print(f"{'='*70}\n")

    # Initialize server
    config = ServerConfig()
    server = MemoryRAGServer(config)
    await server.initialize()

    start_time = time.time()
    created_count = 0
    errors = 0

    # Calculate category counts
    category_counts = {
        cat: int(size * pct) for cat, pct in category_distribution.items()
    }

    # Adjust for rounding errors
    total = sum(category_counts.values())
    if total < size:
        category_counts[MemoryCategory.FACT] += size - total

    print("Category Distribution:")
    for cat, count in category_counts.items():
        print(f"  {cat.value}: {count:,} ({count/size*100:.1f}%)")
    print()

    # Generate memories
    for category, count in category_counts.items():
        print(f"\nGenerating {category.value} memories ({count:,})...")

        for i in range(count):
            try:
                content = generate_random_content(category)

                # Random timestamps over the past year
                days_ago = random.randint(0, 365)
                datetime.now(UTC) - timedelta(days=days_ago)

                # Random importance (biased towards medium)
                importance = random.gauss(0.5, 0.2)
                importance = max(0.0, min(1.0, importance))

                # Random context level
                if category == MemoryCategory.PREFERENCE:
                    context_level = ContextLevel.CORE_IDENTITY
                elif category == MemoryCategory.SESSION_STATE:
                    context_level = ContextLevel.CONVERSATION
                else:
                    context_level = random.choice(
                        [
                            ContextLevel.CORE_IDENTITY,
                            ContextLevel.PROJECT_SPECIFIC,
                            ContextLevel.CONVERSATION,
                        ]
                    )

                # Random tags (1-3 tags)
                tag_pool = [
                    "python",
                    "javascript",
                    "web",
                    "api",
                    "testing",
                    "deployment",
                    "database",
                    "security",
                    "performance",
                ]
                num_tags = random.randint(1, 3)
                tags = random.sample(tag_pool, num_tags)

                # Store memory
                await server.store_memory(
                    content=content,
                    category=category.value,
                    importance=importance,
                    tags=tags,
                    context_level=context_level.value,
                )

                created_count += 1

                # Progress indicator
                if created_count % 100 == 0:
                    elapsed = time.time() - start_time
                    rate = created_count / elapsed
                    remaining = (size - created_count) / rate if rate > 0 else 0
                    print(
                        f"  Progress: {created_count:,}/{size:,} "
                        f"({created_count/size*100:.1f}%) - "
                        f"{rate:.1f} mem/sec - "
                        f"ETA: {remaining:.0f}s",
                        end="\r",
                    )

            except Exception as e:
                errors += 1
                if errors <= 5:  # Only print first 5 errors
                    print(f"\n  Error creating memory: {e}")

    elapsed = time.time() - start_time

    print(f"\n\n{'='*70}")
    print("Generation Complete")
    print(f"{'='*70}")
    print(f"Total Memories: {created_count:,}")
    print(f"Errors: {errors}")
    print(f"Time Elapsed: {elapsed:.2f}s")
    print(f"Average Rate: {created_count/elapsed:.1f} memories/sec")
    print(f"Database: {output_name}")
    print(f"{'='*70}\n")

    await server.close()


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate test database for performance testing"
    )
    parser.add_argument(
        "size",
        type=int,
        choices=[1000, 10000, 50000],
        help="Number of memories to generate (1K, 10K, or 50K)",
    )
    parser.add_argument(
        "--name", default=None, help="Custom name for the test database"
    )

    args = parser.parse_args()

    name = args.name or f"perf_test_{args.size//1000}k"

    await generate_test_database(args.size, name)


if __name__ == "__main__":
    asyncio.run(main())
