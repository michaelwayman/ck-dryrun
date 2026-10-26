# Agent guide

This project replaces a WordPress brand-reviews site with a Django app, a separate Django auth service, a shared token library, a React `<BrandList />` component and an SCSS tree. Brief: [CHALLENGE.md](CHALLENGE.md), which is read-only. Spec: [SPEC.md](SPEC.md). Research: [docs/research.md](docs/research.md). Contracts: [docs/contracts/](docs/contracts/).

The project is built with the challenge-kit plugin. Work is tracked on GitHub through milestones, issues and the Project linked at the top of [SPEC.md](SPEC.md).

## Roles

- The **user** owns `SPEC.md`: what gets built, what doesn't, and the priorities. It changes only through `/challenge-kit:change-spec`.
- The **orchestrator** session (`/challenge-kit:orchestrate`) owns the contracts and the Integration milestone. It plans rounds, starts workers and answers their questions. It never builds service code and never merges.
- A **worker** session (`/challenge-kit:work-issue <n>`) builds one issue in its own worktree, opens one PR and stops. The user merges.

## Boundaries

- A worker edits only its issue's `Touches:` paths.
- Contracts change only through a `contract` issue. A worker that needs a change stops and messages the orchestrator.
- Each side tests against the contract's examples, never against another service's code or branch.

### Services
- **app** (`services/app/`)
  - Owns: industries, brands and reviews in `app-db`; the pages; `/api/brands/`; `import_wp`.
  - Trusts: Bearer access tokens, verified locally with `tokenauth` against `AUTH_PUBLIC_KEYS`. It never calls auth at request time.
  - Talks to: WP `db` only through the [wp-source](docs/contracts/wp-source.md) contract.
- **auth** (`services/auth/`)
  - Owns: users, password hashes, roles, refresh tokens, the signing key and `/admin/`, all in `auth-db`; `import_wp_users`.
  - Trusts: credentials, refresh tokens, and Django sessions for admin.
  - Mints tokens per [access-token](docs/contracts/access-token.md).
- **frontend** (`frontend/`)
  - Owns: the `<BrandList />` source and the SCSS tree. It is build-only; the app image serves the output.
  - Talks to: the app only through [brands-api](docs/contracts/brands-api.md) and [brandlist-mount](docs/contracts/brandlist-mount.md).
- **tokenauth** (`libs/tokenauth/`)
  - Owns: token verification, the claim schema, role constants and the DRF classes, per [shared-lib](docs/contracts/shared-lib.md).
  - Has no Django dependency in its core. Never put login, minting, keys or the WP hasher here.
- **WP stack** (`db`, `wordpress`, `phpmyadmin`, `wp-content/`, `db/dump.sql`)
  - Read-only source. Never modify it.

## Working rules

### Scope
- Build only what the issue's `Delivers: R<n>` and its approved Decisions cover. A new capability is a question for `change-spec`, not a call you make.
- Nothing on SPEC.md's out-of-scope list (`O<n>`) gets built, even partly.
- Stay inside the issue's `Touches:` paths: one service, one layer. An endpoint, the page that shows it, a build step and a component are separate issues.
- Stay inside the size budget. Going well over it means stop and ask, not open the PR.
- List every choice the issue didn't decide under "Calls I made" in the PR.

### Correctness
- Check library APIs against the installed code, not memory.
- Before picking a version, check the peer ranges of every package that depends on it, and note why it's pinned next to the pin.
- Make the schema as strict as the source data guarantees: NOT NULL, CHECK and unique constraints wherever every row satisfies them. A field that's legitimately empty in some states stays nullable; there, handle null in every query, sort and serializer that reads it.
- Contracts are the only agreement between services. Test against the contract's examples, never against another service's code or branch.

### Data and secrets
- Never put real user data or credentials in code, tests, fixtures or commits, even when they're already elsewhere in the repo (a seed dump, a fixture). Generate stand-in data. If you must keep real data, ask first and flag it in the PR.

### Process
- Write the code and its tests together, then run them. While working, run only the targets the change touches. Run `make check` once, before the PR.
- Done means `make check` passes. Report what you ran and what it printed.
- Before building tooling for the agent, check whether a built-in Claude Code feature already does it.

## Review rules

<!-- Project-specific checks the reviewer enforces on every PR. Added by /challenge-kit:record-correction. -->

## Learned rules

<!-- Corrections turned into rules by /challenge-kit:record-correction. Newest last. Each: the rule, then (YYYY-MM-DD, trigger #n). -->
