# AtomicBot Bridge v2

Denne mappen inneholder en GitHub Actions-workflow som automatisk pusher alle filer fra `agent_outbox/` til repoet.

## Hvordan bruke

1. Legg filer du vil pushe i `agent_outbox/`
2. GitHub Actions (`bridge_push.yml`) flytter filene til roten og committer
3. Endringene vises i GitHub med melding "Bridge auto-push from agent_outbox"
