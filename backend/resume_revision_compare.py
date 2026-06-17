from .document_service import get_current_resume, read_markdown_document
from .resume_revision_draft_export import read_resume_revision_draft_export


def compare_resume_revision_with_current(file_name: str) -> dict:
    draft = read_resume_revision_draft_export(file_name)
    current_resume = get_current_resume()
    warnings = [
        "This is a read-only comparison.",
        "No real resume, job description, index, or source document was modified.",
        "This comparison does not trigger indexing, LLM calls, platform access, or auto-apply actions.",
    ]

    current_resume_content = ""
    current_resume_readable = False
    if current_resume:
        try:
            current_resume_content = read_markdown_document(
                "resumes",
                current_resume["name"],
                source=current_resume["source"],
            )
            current_resume_readable = True
        except ValueError:
            warnings.append("Current resume exists, but only Markdown resumes can be compared inline.")
        except FileNotFoundError:
            warnings.append("Current resume metadata exists, but the file could not be read.")
    else:
        warnings.append("No current resume is set.")

    return {
        "file_name": draft["file_name"],
        "relative_path": draft["relative_path"],
        "current_resume": current_resume,
        "current_resume_readable": current_resume_readable,
        "current_resume_content": current_resume_content,
        "resume_diff_content": draft["content"],
        "warnings": dedupe(warnings),
    }


def dedupe(values: list[str]) -> list[str]:
    results = []
    for value in values:
        if value and value not in results:
            results.append(value)
    return results
