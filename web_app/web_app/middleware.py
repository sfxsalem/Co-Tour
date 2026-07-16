class SecurityHeadersMiddleware:
    """Apply a restrictive baseline CSP compatible with the existing map UI."""

    policy = "; ".join(
        (
            "default-src 'self'",
            "base-uri 'self'",
            "object-src 'none'",
            "frame-ancestors 'none'",
            "form-action 'self'",
            "img-src 'self' data: https:",
            "font-src 'self' data: https://fonts.gstatic.com https://ka-f.fontawesome.com",
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com https://stackpath.bootstrapcdn.com https://unpkg.com",
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://code.jquery.com https://kit.fontawesome.com https://stackpath.bootstrapcdn.com https://unpkg.com",
            "connect-src 'self' https://ka-f.fontawesome.com https://nominatim.openstreetmap.org",
            "upgrade-insecure-requests",
        )
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", self.policy)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response
