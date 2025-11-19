"""Review comment generation."""

from dataclasses import dataclass
from typing import Optional

from .pattern_matcher import PatternMatch


@dataclass
class ReviewComment:
    """Represents a code review comment."""

    pattern_id: str
    pattern_name: str
    category: str
    severity: str
    file_path: str
    line_number: int
    description: str
    suggested_fix: str
    confidence: str
    similarity_score: float
    code_excerpt: Optional[str] = None


class ReviewCommentGenerator:
    """Generate human-readable code review comments."""

    def generate_comment(
        self,
        match: PatternMatch,
        file_path: str,
        line_number: int,
        code_excerpt: Optional[str] = None,
    ) -> ReviewComment:
        """
        Generate a review comment for a pattern match.

        Args:
            match: The pattern match
            file_path: Path to the file containing the issue
            line_number: Line number where the issue occurs
            code_excerpt: Optional code snippet showing the issue

        Returns:
            ReviewComment object with all details
        """
        return ReviewComment(
            pattern_id=match.pattern.id,
            pattern_name=match.pattern.name,
            category=match.pattern.category,
            severity=match.pattern.severity,
            file_path=file_path,
            line_number=line_number,
            description=match.pattern.description,
            suggested_fix=match.pattern.fix_description,
            confidence=match.confidence,
            similarity_score=match.similarity_score,
            code_excerpt=code_excerpt or match.matched_code[:200],  # Limit to 200 chars
        )

    def format_as_markdown(self, comment: ReviewComment) -> str:
        """
        Format a review comment as markdown.

        Args:
            comment: The review comment to format

        Returns:
            Markdown-formatted review comment
        """
        # Emoji for severity
        severity_emoji = {
            "critical": "🚨",
            "high": "⚠️",
            "medium": "⚡",
            "low": "💡",
        }
        emoji = severity_emoji.get(comment.severity, "ℹ️")

        # Category badge
        category_badge = {
            "security": "🔒 Security",
            "performance": "⚡ Performance",
            "maintainability": "🔧 Maintainability",
            "best_practice": "✅ Best Practice",
        }
        badge = category_badge.get(comment.category, comment.category.title())

        markdown = f"""### {emoji} {comment.pattern_name}

**{badge}** | **Severity**: {comment.severity.upper()} | **Confidence**: {comment.confidence}

**Location**: `{comment.file_path}:{comment.line_number}`

**Issue**: {comment.description}

**Suggested Fix**: {comment.suggested_fix}
"""

        if comment.code_excerpt:
            # Truncate if too long
            excerpt = comment.code_excerpt
            if len(excerpt) > 200:
                excerpt = excerpt[:200] + "..."

            markdown += f"""
**Code Excerpt**:
```
{excerpt}
```
"""

        markdown += f"\n---\n*Detection confidence: {comment.similarity_score:.2%}*\n"

        return markdown

    def generate_summary(
        self,
        comments: list[ReviewComment],
    ) -> dict:
        """
        Generate a summary of review comments.

        Args:
            comments: List of review comments

        Returns:
            Dict with summary statistics
        """
        summary = {
            "total_issues": len(comments),
            "by_severity": {},
            "by_category": {},
            "by_confidence": {},
            "critical_count": 0,
            "high_count": 0,
        }

        for comment in comments:
            # Count by severity
            severity = comment.severity
            summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + 1

            # Count by category
            category = comment.category
            summary["by_category"][category] = summary["by_category"].get(category, 0) + 1

            # Count by confidence
            confidence = comment.confidence
            summary["by_confidence"][confidence] = summary["by_confidence"].get(confidence, 0) + 1

            # Track critical and high
            if severity == "critical":
                summary["critical_count"] += 1
            elif severity == "high":
                summary["high_count"] += 1

        return summary
