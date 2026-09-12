# Role: Backend

Stacks: Laravel/PHP, Spring Boot/Java, Node.js, Python, PostgreSQL/MariaDB.

## Do
- Validate input at the boundary. Never trust a request body.
- Use parameterized queries. No string-built SQL.
- Keep controllers thin; business logic in services.
- New migrations only forward; never edit a migration that has shipped.

## Required checks
- [ ] Unit test for new logic
- [ ] Integration/API test for new or changed endpoints
- [ ] Build/compile passes
- [ ] Backward compatibility noted for any changed response shape

## Report additions
- Endpoints changed (method + path + auth requirement)
- Migrations added (and the rollback story)
- Breaking changes, explicitly yes or no
