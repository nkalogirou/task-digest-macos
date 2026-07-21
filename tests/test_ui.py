from task_digest.ui import SIMPLE_PAGE_CSS, brand_html, navigation_html


def test_navigation_has_all_primary_destinations() -> None:
    rendered = navigation_html(active_path="/settings")
    assert 'href="/"' in rendered
    assert 'href="/standup"' in rendered
    assert 'href="/settings"' in rendered
    assert 'href="/rules"' in rendered
    assert 'href="/relationships"' in rendered
    assert 'aria-current="page"' in rendered


def test_brand_and_shared_styles_are_present() -> None:
    assert "Task Digest" in brand_html()
    assert ".app-sidebar" in SIMPLE_PAGE_CSS
    assert "prefers-color-scheme:dark" in SIMPLE_PAGE_CSS
