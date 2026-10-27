SHELL := /bin/bash
COMPOSE := docker compose
WPCLI := $(COMPOSE) run --rm wpcli

# Every check runs in Docker (C1), identical locally and in CI. One dev image (the app
# Dockerfile's `dev` target) holds ruff, mypy and pytest for the whole uv workspace; the
# `frontend` target holds node_modules for the frontend checks.
DEV_IMAGE := ck-dev
FRONTEND_IMAGE := ck-frontend
PY_MEMBERS := libs/tokenauth services/app services/auth
# Test runs mount docs/contracts (and reference, for the frontend) read-only at the same path
# relative to each package as in the repo, so tests read contract examples and mocks in place.
CONTRACTS := $(CURDIR)/docs/contracts
DEV_RUN := docker run --rm $(DEV_IMAGE)
DEV_TEST_MOUNTS := -v "$(CONTRACTS):/workspace/docs/contracts:ro"
FRONTEND_RUN := docker run --rm -v "$(CONTRACTS):/docs/contracts:ro" -v "$(CURDIR)/reference:/reference:ro" $(FRONTEND_IMAGE)
# Write targets bind-mount the source and run as the host user, so the host owns what they write.
HOST_USER := --user $$(id -u):$$(id -g)

# CI sets BUILDX_CACHE to a directory restored by actions/cache; buildx reads each image's cache
# from there and writes a fresh one next to it, which CI then rotates into place (so the cache
# doesn't grow without bound). Locally it is empty and the daemon's own layer cache is used.
BUILDX_CACHE ?=
comma := ,
cache_flags = $(if $(BUILDX_CACHE),--cache-from type=local$(comma)src=$(BUILDX_CACHE)/$(1) --cache-to type=local$(comma)dest=$(BUILDX_CACHE)-new/$(1)$(comma)mode=max)

.PHONY: help up down restart logs reset wp bootstrap dump status \
	dev-image frontend-image lint fmt-check typecheck test check fmt lint-fix css migrate

help:
	@echo "Targets:"
	@echo "  up              Build and start everything (WP stack, app, auth and their databases)"
	@echo "  down            Stop containers (preserve data)"
	@echo "  restart         Restart running containers"
	@echo "  reset           Stop containers AND wipe every volume (WP db, app-db, auth-db, dev keys)"
	@echo "  logs            Tail wordpress + db logs"
	@echo "  wp ARGS=\"...\" Run wp-cli inside the stack (e.g. make wp ARGS=\"plugin list\")"
	@echo "  bootstrap       One-shot: install WP core + plugins + seed all content"
	@echo "  dump            Export current DB to db/dump.sql"
	@echo "  status          Show running services"
	@echo "  migrate         Migrate app and auth, then import WP content and users"
	@echo "  check           lint + fmt-check + typecheck + test (the CI gate)"
	@echo "  lint            ruff, eslint and stylelint"
	@echo "  fmt-check       ruff format and prettier, check only"
	@echo "  typecheck       mypy per Python member, tsc for the frontend"
	@echo "  test            tokenauth (no Django, then its drf tests), app, auth and frontend suites"
	@echo "  fmt             Apply ruff format and prettier"
	@echo "  lint-fix        Apply ruff's and eslint's fixes"
	@echo "  css             Compile frontend/scss into frontend/dist/css"

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

reset:
	@echo "Wiping volumes db_data (WP), app_db_data, auth_db_data and dev_keys (signing key)."
	$(COMPOSE) down -v
	@echo "Volumes wiped. Run 'make up' to start fresh from db/dump.sql, then 'make migrate'."

logs:
	$(COMPOSE) logs -f wordpress db

wp:
	$(WPCLI) $(ARGS)

bootstrap:
	$(COMPOSE) run --rm --entrypoint bash wpcli /scripts/seed.sh

dump:
	@mkdir -p db
	$(COMPOSE) exec db sh -c 'mariadb-dump -u root -p"$$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 --add-drop-table --skip-extended-insert "$$MYSQL_DATABASE"' > db/dump.sql
	@echo "Wrote db/dump.sql ($$(wc -l < db/dump.sql) lines)"

status:
	$(COMPOSE) ps

# Each import runs only once its service ships the command (M9); until then it is skipped.
migrate:
	$(COMPOSE) run --rm app sh -c 'python manage.py migrate && \
		if python manage.py help --commands | grep -qx import_wp; then python manage.py import_wp; \
		else echo "import_wp not available yet, skipped"; fi'
	$(COMPOSE) run --rm auth sh -c 'python manage.py migrate && \
		if python manage.py help --commands | grep -qx import_wp_users; then python manage.py import_wp_users; \
		else echo "import_wp_users not available yet, skipped"; fi'

# --- Checks ----------------------------------------------------------------------------------

dev-image:
	docker buildx build --load --target dev -f services/app/Dockerfile -t $(DEV_IMAGE) $(call cache_flags,dev) .

frontend-image:
	docker buildx build --load --target frontend -f services/app/Dockerfile -t $(FRONTEND_IMAGE) $(call cache_flags,frontend) .

check: lint fmt-check typecheck test

lint: dev-image frontend-image
	@set -e; for m in $(PY_MEMBERS); do echo "ruff check $$m"; \
		docker run --rm -w /workspace/$$m $(DEV_IMAGE) ruff check .; done
	$(FRONTEND_RUN) npm run lint
	$(FRONTEND_RUN) npm run lint:css

fmt-check: dev-image frontend-image
	@set -e; for m in $(PY_MEMBERS); do echo "ruff format --check $$m"; \
		docker run --rm -w /workspace/$$m $(DEV_IMAGE) ruff format --check .; done
	$(FRONTEND_RUN) npm run format:check

# DJANGO_DEBUG is already set in the dev image; passed again because mypy's Django plugin loads
# settings, which refuse to load without a secret key unless debug is on.
typecheck: dev-image frontend-image
	@set -e; for m in $(PY_MEMBERS); do echo "mypy $$m"; \
		docker run --rm -e DJANGO_DEBUG=true -w /workspace/$$m $(DEV_IMAGE) mypy; done
	$(FRONTEND_RUN) npm run typecheck

# tokenauth runs in a bare python image with only its own [test] extra, which proves its core
# has no Django dependency (C5); its drf-marked tests then run in the dev image. The bare run
# copies the package to /tmp/tokenauth, so tests/../../../docs resolves to /docs as in the repo.
# No suite needs a database yet; DB-backed tests add the Postgres services they need in their
# own issues.
test: dev-image frontend-image
	docker run --rm -v "$(CURDIR)/libs/tokenauth:/src:ro" -v "$(CONTRACTS):/docs/contracts:ro" python:3.14-slim sh -c \
		'cp -r /src /tmp/tokenauth && cd /tmp/tokenauth && pip install --quiet --root-user-action=ignore ".[test]" && pytest -p no:cacheprovider'
	docker run --rm $(DEV_TEST_MOUNTS) -w /workspace/libs/tokenauth $(DEV_IMAGE) pytest -p no:cacheprovider -m drf
	docker run --rm $(DEV_TEST_MOUNTS) -w /workspace/services/app $(DEV_IMAGE) pytest
	docker run --rm $(DEV_TEST_MOUNTS) -w /workspace/services/auth $(DEV_IMAGE) pytest
	$(FRONTEND_RUN) npm test

# --- Write targets: change files on the host --------------------------------------------------

# The anonymous volume keeps the image's node_modules under the bind mount.
FRONTEND_WRITE := docker run --rm $(HOST_USER) -v "$(CURDIR)/frontend:/frontend" -v /frontend/node_modules $(FRONTEND_IMAGE)
DEV_WRITE := docker run --rm $(HOST_USER) -v "$(CURDIR):/workspace" -w /workspace $(DEV_IMAGE)

fmt: dev-image frontend-image
	$(DEV_WRITE) ruff format $(PY_MEMBERS)
	$(FRONTEND_WRITE) npm run format

lint-fix: dev-image frontend-image
	$(DEV_WRITE) ruff check --fix $(PY_MEMBERS)
	$(FRONTEND_WRITE) npx eslint --fix .

# build:css skips itself until frontend/scss/main.scss exists.
css: frontend-image
	$(FRONTEND_WRITE) npm run build:css
