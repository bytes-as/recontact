# Recontact

Decision support for genetic counsellors. When a classification in ClinVar changes, Recontact works out who must be told, by whom, whether a permitted path exists, and which decisions made on the old class must reopen.

People, families, clinicians and organisations in the demo are fictional. ClinVar records are public NCBI data. Nothing is sent without a named counsellor's approval. This is not medical advice.

Build status is the checklist in `docs/GOALS.md`.

## Run locally

Requires Docker and Python 3.12.

```bash
cp .env.example .env   # set ADMIN_TOKEN
docker compose up -d
```

The API is on port 8000 and FalkorDB Browser on port 3000. The web app runs separately:

```bash
cd apps/web && npm install && npm run dev -- -p 3001
```

If those ports are already taken, stop the other stack first. The compose file keeps 6379, 3000 and 8000 because that is what the project contract checks.
