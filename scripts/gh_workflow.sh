#!/usr/bin/env bash
# Lanza un workflow de GitHub Actions, espera a que termine y muestra pasos + anotaciones (::notice / ::error).
# Útil cuando los logs no se pueden descargar (proxy): el resultado viaja en las anotaciones.
#   scripts/gh_workflow.sh publish_dashboard.yml
#   scripts/gh_workflow.sh daily_sr.yml -f 'inputs[dry_run]=true' -f 'inputs[scope]=all' -f 'inputs[as_of]='
set -uo pipefail
WF="${1:?workflow .yml}"; shift
REPO="${GH_REPO:-richcruz1981/AI_M8_FinalAssignment_SPM_SR}"
R="repos/$REPO"
before=$(gh api "$R/actions/workflows/$WF/runs?per_page=1" --jq '.workflow_runs[0].id // 0')
gh api -X POST "$R/actions/workflows/$WF/dispatches" -f ref=main "$@" || exit 1
for _ in $(seq 1 30); do
  ID=$(gh api "$R/actions/workflows/$WF/runs?per_page=1" --jq '.workflow_runs[0].id // 0')
  [ "$ID" != "$before" ] && break; sleep 4
done
for _ in $(seq 1 90); do
  s=$(gh api "$R/actions/runs/$ID" --jq '.status+" "+(.conclusion//"")'); [ "${s%% *}" = completed ] && break; sleep 10
done
echo "== $WF · run $ID · $s"
gh api "$R/actions/runs/$ID/jobs" --jq '.jobs[0].steps[] | select(.conclusion != "success" and .conclusion != "skipped") | "  paso: \(.name) -> \(.conclusion)"'
CR=$(gh api "$R/actions/runs/$ID/jobs" --jq '.jobs[0].id')
gh api "$R/check-runs/$CR/annotations" --jq '.[] | "  [\(.annotation_level)] \(.title // ""): \(.message)"' | grep -v "Node.js 20\|ubuntu-latest label"
[ "${s#* }" = "success" ]
