from playwright.async_api import Page


async def apply_stealth(page: Page):
    """Apply basic anti-detection measures to a Playwright page."""
    await page.add_init_script("""
        // Override navigator.webdriver
        Object.defineProperty(navigator, 'webdriver', {
            get: () => false,
        });

        // Override chrome runtime
        window.chrome = {
            runtime: {},
        };

        // Override permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters);

        // Override plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });

        // Override languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['fr-FR', 'fr', 'en-US', 'en'],
        });
    """)
