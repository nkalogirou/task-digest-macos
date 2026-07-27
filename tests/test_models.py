

def test_github_link_has_pr_cockpit_fields() -> None:
    from task_digest.models import GitHubCheckDetail, GitHubLink, GitHubReviewDetail, GitHubReviewThread

    link = GitHubLink(owner="example-org", repo="web-app", number=42, url="https://github.com/example-org/web-app/pull/42")
    link.checks.append(GitHubCheckDetail(name="tests", state="SUCCESS", bucket="pass"))
    link.reviews.append(GitHubReviewDetail(reviewer="reviewer", state="APPROVED"))
    link.unresolved_threads.append(GitHubReviewThread(id="thread-1", author="reviewer", body="Please adjust this.", path="tests/test_app.py"))

    assert link.checks[0].name == "tests"
    assert link.reviews[0].state == "APPROVED"
    assert link.unresolved_threads[0].path == "tests/test_app.py"
