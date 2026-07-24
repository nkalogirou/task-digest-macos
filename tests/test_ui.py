from task_digest.ui import SIMPLE_PAGE_CSS, brand_html, navigation_html


def test_navigation_has_all_primary_destinations() -> None:
    rendered = navigation_html(active_path="/settings")
    assert 'href="/"' in rendered
    assert 'href="/standup"' in rendered
    assert 'href="/settings"' in rendered
    assert 'href="/rules"' in rendered
    assert 'href="/relationships"' in rendered
    assert 'aria-current="page"' in rendered


def test_navigation_groups_related_destinations() -> None:
    rendered = navigation_html(active_path="/system")
    assert rendered.index('>Work<') < rendered.index('href="/standup"')
    assert rendered.index('>Organize<') < rendered.index('href="/rules"')
    assert rendered.index('>Review<') < rendered.index('href="/history"')
    assert rendered.index('>System<') < rendered.index('href="/settings"')
    assert 'System status' in rendered
    assert rendered.count('class="app-nav-group"') == 4


def test_brand_and_shared_styles_are_present() -> None:
    assert "Task Digest" in brand_html()
    assert ".app-sidebar" in SIMPLE_PAGE_CSS
    assert "prefers-color-scheme:dark" in SIMPLE_PAGE_CSS


def test_command_palette_assets_include_shortcut_and_navigation() -> None:
    from task_digest.ui import command_palette_html, command_palette_script

    rendered = command_palette_html()
    script = command_palette_script("http://127.0.0.1:8765")
    assert 'id="command-palette-backdrop"' in rendered
    assert "⌘K" in rendered
    assert "Open Settings" in script
    assert "TaskDigestCommandPalette" in script
    assert "metaKey" in script
