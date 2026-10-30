# PMO development instructions

- Read README.md and docs/COLLABORATION.md. This repository is the canonical source; frontend/ is the website source. Do not confuse the separate Sites hosting staging repository with GitHub.
- Never commit/upload/overwrite live data/, SQLite snapshots, credentials, session tokens, member codes, runtime receiver.json or .env files. Production records stay on the owner's central backend (Cloudflare D1 after cloud migration); collaborators use authenticated /team access. See docs/CLOUD.md. Private cloud/wrangler.local.json and cloud/public build output are ignored. Cloudflare migration to the owner's account is authorized; do not upload records to GitHub.
- Before new work inspect status and fetch the relevant remote. Preserve unrelated changes. Current user authorizes tested source changes to be committed and pushed to feature branches. External collaborators fork and submit PRs. Do not force-push or claim unpushed changes are synchronized.
- Run python test_server.py for backend, database and access-control changes; tests use temporary databases. Database migrations must preserve production records.
- No hardcoded personal computer paths or embedded secrets in new code. Development local databases are not production.
- Attachments, evidence approval, real LLM Agent, OnePager and fine-grained project viewer roles are not implemented; do not claim otherwise.
- Keep docs current. Commit/push and restart/publish are separate actions. Review concrete diffs and tests before mainline merges.
