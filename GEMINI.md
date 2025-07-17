environment:
  - Store all secrets and credentials in .env files, never in code.
  - Use os.getenv for all sensitive settings with appropriate defaults.
  - Set DEBUG = False in production.
  - Restrict ALLOWED_HOSTS to trusted domains in production.
  - Uncomment and enable all security middleware and settings before deploying.
  - Use python-decouple or django-environ for better environment variable management.
  - Log sensitive configuration issues but never log credential values.

static_and_media:
  - Use STATIC_ROOT and STATICFILES_STORAGE as configured.
  - Store user uploads in MEDIA_ROOT and serve via MEDIA_URL.
  - Validate all uploaded files for type, size, and content.
  - Use cloud storage (AWS S3, Cloudinary) for production media files.
  - Implement file virus scanning for user uploads.
  - Set appropriate file retention policies.

database:
  - Use PostgreSQL in production and development for consistency.
  - Never commit database credentials to version control.
  - Use dj_database_url for dynamic database configuration.
  - Implement database connection pooling for performance.
  - Use database migrations properly with descriptive names.
  - Set up database backups and recovery procedures.
  - Use database indexes for frequently queried fields.

rest_api:
  - Follow RESTful conventions strictly for all endpoints.
  - Specify filterset_fields, search_fields, and ordering_fields in ViewSets.
  - Use pagination for all list endpoints with configurable page sizes.
  - Document all endpoints with comprehensive docstrings and examples.
  - Use API versioning (v1/, v2/) for breaking changes.
  - Implement proper HTTP status codes and error responses.
  - Use serializers for input validation and output formatting.
  - Cache frequently accessed read-only data.

authentication_and_permissions:
  - Use explicit permission classes for all API views.
  - Implement role-based access control (RBAC) where appropriate.
  - Restrict write operations to authenticated users or admins.
  - Never expose sensitive user data via the API.
  - Use JWT tokens for stateless authentication in API-first applications.
  - Implement rate limiting to prevent abuse.
  - Log authentication attempts and failures.

cors:
  - Only allow trusted origins in CORS_ALLOWED_ORIGINS.
  - Never use CORS_ALLOW_ALL_ORIGINS in production.
  - Specify allowed methods and headers explicitly.
  - Use CORS_ALLOW_CREDENTIALS only when necessary.

email:
  - Configure email settings via environment variables.
  - Never hardcode email credentials.
  - Use a default no-reply address for outgoing mail.
  - Implement email templates with proper HTML and plain text versions.
  - Use Django signals for automated email notifications.
  - Implement email queue for high-volume sending.
  - Add unsubscribe functionality for marketing emails.
  - Test email delivery in staging environments.

ai_integration:
  - Use consistent naming conventions that AI can easily understand.
  - Structure code with clear separation of concerns.
  - Implement comprehensive logging for AI debugging.
  - Use type hints throughout the codebase for better AI comprehension.
  - Create utility functions for common AI integration patterns.
  - Document AI-specific configuration and endpoints.
  - Implement webhook endpoints for AI service callbacks.
  - Use standardized response formats for AI consumption.

code_organization:
  - Group related models, serializers, and views by app functionality.
  - Use clear, descriptive names following Python/Django conventions.
  - Keep utility functions in dedicated modules (utils/, helpers/).
  - Separate business logic from view logic using services/managers.
  - Use constants files for magic numbers and strings.
  - Implement proper package structure with __init__.py files.
  - Follow DRY principles but prioritize readability over brevity.

performance:
  - Use select_related and prefetch_related to optimize database queries.
  - Implement caching strategies for frequently accessed data.
  - Use database indexes on foreign keys and frequently filtered fields.
  - Profile and monitor application performance regularly.
  - Implement pagination for large datasets.
  - Use background tasks for time-consuming operations.

error_handling:
  - Implement comprehensive error handling with informative messages.
  - Use custom exception classes for application-specific errors.
  - Log errors with appropriate detail levels.
  - Provide user-friendly error responses in APIs.
  - Implement global exception handlers for common error patterns.
  - Never expose internal error details to end users.

testing:
  - Write unit tests for all models, serializers, and API endpoints.
  - Use factories or fixtures for test data creation.
  - Implement integration tests for complex workflows.
  - Achieve at least 80% code coverage.
  - Use mocking for external service dependencies.
  - Write performance tests for critical endpoints.
  - Implement automated testing in CI/CD pipelines.

security:
  - Validate and sanitize all user inputs.
  - Use Django's built-in CSRF protection.
  - Implement proper SQL injection prevention.
  - Use HTTPS everywhere in production.
  - Implement security headers and CSP policies.
  - Regular security audits and dependency updates.
  - Use environment-specific security configurations.

monitoring_and_logging:
  - Implement structured logging with appropriate log levels.
  - Use correlation IDs for tracking requests across services.
  - Monitor application performance and error rates.
  - Set up alerts for critical system events.
  - Log business events for analytics and debugging.
  - Never log sensitive information (passwords, tokens, PII).

documentation:
  - Maintain up-to-date docstrings for all public classes and methods.
  - Provide comprehensive API documentation (OpenAPI/Swagger).
  - Document deployment procedures and environment setup.
  - Create user guides and integration examples.
  - Document database schema and migrations.
  - Maintain a changelog for API versions.
  - Use clear commit messages following conventional commits.
