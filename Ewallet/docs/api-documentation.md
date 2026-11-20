# API documentation
All endpoints are prefixed `/api`.

- `GET /health`
- `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `PUT /auth/password`
- `GET /dashboard`
- `GET|POST /accounts`
- `GET|POST /categories`, `PUT|DELETE /categories/{id}`
- `GET|POST /transactions`, `PUT|DELETE /transactions/{id}`
- `GET|POST /budgets`, `PUT|DELETE /budgets/{id}`
- `GET /reports`
- `GET|POST /notes`, `PUT|DELETE /notes/{id}`
- `GET|POST /vault`, `POST /vault/{id}/reveal`, `DELETE /vault/{id}`
- `GET|PUT /profile`, `GET|PUT /settings`

Requests and responses use JSON. Authenticated endpoints require the Flask session cookie. Errors use `{"success":false,"error":"..."}`.
