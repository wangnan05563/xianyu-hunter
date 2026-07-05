# Rule Catalog — Architecture

## Scope
- Covers: controller/service/core-domain/libs/model layering, dependency direction, responsibility placement, repository abstraction, observability-friendly flow.

## Rules

### Keep business logic out of controllers
- Category: maintainability
- Severity: critical
- Description: Controllers should parse input, call services, and return serialized responses. Business decisions inside controllers make behavior hard to reuse and test.
- Suggested fix: Move domain/business logic into the service or core/domain layer. Keep controller handlers thin and orchestration-focused.
- Example:
  - Bad:
    ```python
    @bp.post("/apps/<app_id>/publish")
    def publish_app(app_id: str):
        payload = request.get_json() or {}
        if payload.get("force") and current_user.role != "admin":
            raise ValueError("only admin can force publish")
        app = App.query.get(app_id)
        app.status = "published"
        db.session.commit()
        return {"result": "ok"}
    ```
  - Good:
    ```python
    @bp.post("/apps/<app_id>/publish")
    def publish_app(app_id: str):
        payload = PublishRequest.model_validate(request.get_json() or {})
        app_service.publish_app(app_id=app_id, force=payload.force, actor_id=current_user.id)
        return {"result": "ok"}
    ```

### Preserve layer dependency direction
- Category: best practices
- Severity: critical
- Description: Controllers may depend on services, and services may depend on core/domain abstractions. Reversing this direction (for example, core importing controller/web modules) creates cycles and leaks transport concerns into domain code.
- Suggested fix: Extract shared contracts into core/domain or service-level modules and make upper layers depend on lower, not the reverse.
- Example:
  - Bad:
    ```python
    # core/policy/publish_policy.py
    from controllers.console.app import request_context

    def can_publish() -> bool:
        return request_context.current_user.is_admin
    ```
  - Good:
    ```python
    # core/policy/publish_policy.py
    def can_publish(role: str) -> bool:
        return role == "admin"

    # service layer adapts web/user context to domain input
    allowed = can_publish(role=current_user.role)
    ```

### Keep libs business-agnostic
- Category: maintainability
- Severity: critical
- Description: Modules under `api/libs/` should remain reusable, business-agnostic building blocks. They must not encode product/domain-specific rules, workflow orchestration, or business decisions.
- Suggested fix:
  - If business logic appears in `api/libs/`, extract it into the appropriate `services/` or `core/` module and keep `libs` focused on generic, cross-cutting helpers.
  - Keep `libs` dependencies clean: avoid importing service/controller/domain-specific modules into `api/libs/`.
- Example:
  - Bad:
    ```python
    # api/libs/conversation_filter.py
    from services.conversation_service import ConversationService

    def should_archive_conversation(conversation, tenant_id: str) -> bool:
        # Domain policy and service dependency are leaking into libs.
        service = ConversationService()
        if service.has_paid_plan(tenant_id):
            return conversation.idle_days > 90
        return conversation.idle_days > 30
    ```
  - Good:
    ```python
    # api/libs/datetime_utils.py (business-agnostic helper)
    def older_than_days(idle_days: int, threshold_days: int) -> bool:
        return idle_days > threshold_days

    # services/conversation_service.py (business logic stays in service/core)
    from libs.datetime_utils import older_than_days

    def should_archive_conversation(conversation, tenant_id: str) -> bool:
        threshold_days = 90 if has_paid_plan(tenant_id) else 30
        return older_than_days(conversation.idle_days, threshold_days)
    ```

### Reuse or introduce repository abstraction
- Category: maintainability
- Severity: suggestion
- Description: If a table/model already has a repository abstraction, all reads/writes/queries for that table should use the existing repository. If no repository exists, introduce one only when complexity justifies it, such as large/high-volume tables, repeated complex query logic, or likely storage-strategy variation.
- Suggested fix:
  - First check `api/repositories`, `api/core/repositories`, and `api/extensions/*/repositories/` to verify whether the table/model already has a repository abstraction. If it exists, route all operations through it and add missing repository methods instead of bypassing it with ad-hoc SQLAlchemy access.
  - If no repository exists, add one only when complexity warrants it (for example, repeated complex queries, large data domains, or multiple storage strategies), while preserving dependency direction (service/core depends on abstraction; infra provides implementation).
- Example:
  - Bad:
    ```python
    # Existing repository is ignored and service uses ad-hoc table queries.
    class AppService:
        def archive_app(self, app_id: str, tenant_id: str) -> None:
            app = self.session.execute(
                select(App).where(App.id == app_id, App.tenant_id == tenant_id)
            ).scalar_one()
            app.archived = True
            self.session.commit()
    ```
  - Good:
    ```python
    # Case A: Existing repository must be reused for all table operations.
    class AppService:
        def archive_app(self, app_id: str, tenant_id: str) -> None:
            app = self.app_repo.get_by_id(app_id=app_id, tenant_id=tenant_id)
            app.archived = True
            self.app_repo.save(app)

    # If the query is missing, extend the existing abstraction.
    active_apps = self.app_repo.list_active_for_tenant(tenant_id=tenant_id)
    ```
  - Bad:
    ```python
    # No repository exists, but large-domain query logic is scattered in service code.
    class ConversationService:
        def list_recent_for_app(self, app_id: str, tenant_id: str, limit: int) -> list[Conversation]:
            ...
            # many filters/joins/pagination variants duplicated across services
    ```
  - Good:
    ```python
    # Case B: Introduce repository for large/complex domains or storage variation.
    class ConversationRepository(Protocol):
        def list_recent_for_app(self, app_id: str, tenant_id: str, limit: int) -> list[Conversation]: ...

    class SqlAlchemyConversationRepository:
        def list_recent_for_app(self, app_id: str, tenant_id: str, limit: int) -> list[Conversation]:
            ...

    class ConversationService:
        def __init__(self, conversation_repo: ConversationRepository):
            self.conversation_repo = conversation_repo
    ```
