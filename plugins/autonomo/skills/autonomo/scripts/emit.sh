#!/usr/bin/env bash
# emit.sh — write /autonomo progress events to stdout (pretty) and ${AUTONOMO_LOG} (structured)
# in one call. The dual-write contract is the whole point — see references/run-log.md.
#
# Usage:
#   emit.sh phase-start     <phase> <i> <n>
#   emit.sh phase-end       <phase> <i> <n> <duration_s> [k=v ...]
#   emit.sh phase-bail      <phase> <i> <n> <reason>
#   emit.sh stage-start     <phase> <stage>
#   emit.sh stage-progress  <phase> <stage> <done> [<total>]
#   emit.sh stage-end       <phase> <stage> [<duration_s>]
#   emit.sh assumption      <phase> <question> <answer>
#   emit.sh commit          <sha> <subject>
#   emit.sh progress        <phase> <message>
#   emit.sh run-start       <branch>
#
# Required env: AUTONOMO_LOG — absolute path to the run log file (already opened by preflight).
# Optional env: AUTONOMO_STDOUT_LOG — absolute path; when set, mirrors the pretty stdout line
# to that file. Used by eval harnesses that need a file-on-disk copy of the stdout surface
# to grade against. Unset in normal /autonomo runs.

set -euo pipefail

if [ -z "${AUTONOMO_LOG:-}" ]; then
  echo "emit.sh: AUTONOMO_LOG not set; refusing to drop events" >&2
  exit 2
fi

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# Both helpers preserve the one-line-per-event invariant. The structured form additionally
# backslash-escapes embedded double quotes since fields are rendered as key="value".
oneline() { printf '%s' "$1" | tr '\n' ' '; }
escape()  { oneline "$1" | sed 's/"/\\"/g'; }

dual() {
  # Args: pretty_line  structured_line
  printf '%s\n' "$1"
  printf '%s\n' "$2" >> "${AUTONOMO_LOG}"
  if [ -n "${AUTONOMO_STDOUT_LOG:-}" ]; then
    printf '%s\n' "$1" >> "${AUTONOMO_STDOUT_LOG}"
  fi
}

show_help() {
  sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
}

cmd="${1:-}"
shift || true

case "$cmd" in
  phase-start)
    phase="$1"; i="$2"; n="$3"
    dual "→ Phase ${i}/${n} · ${phase} · dispatching" \
         "$(ts) level=info phase=${phase} event=dispatch_start"
    ;;

  phase-end)
    phase="$1"; i="$2"; n="$3"; duration="$4"
    shift 4
    extras_pretty=""
    extras_log=""
    for kv in "$@"; do
      extras_pretty+=" · ${kv}"
      extras_log+=" ${kv}"
    done
    dual "✓ Phase ${i}/${n} · ${phase} · ${duration}s${extras_pretty}" \
         "$(ts) level=info phase=${phase} event=dispatch_end duration_s=${duration}${extras_log}"
    ;;

  phase-bail)
    phase="$1"; i="$2"; n="$3"
    reason_pretty="$(oneline "$4")"; reason_log="$(escape "$4")"
    dual "✗ Phase ${i}/${n} · ${phase} · BLOCKED · ${reason_pretty}" \
         "$(ts) level=warn phase=${phase} event=blocked reason=\"${reason_log}\""
    ;;

  stage-start)
    phase="$1"; stage="$2"
    dual "→ stage ${stage}" \
         "$(ts) level=info phase=${phase} event=stage_start stage=${stage}"
    ;;

  stage-progress)
    phase="$1"; stage="$2"; done_n="$3"; total="${4:-}"
    if [ -n "${total}" ]; then
      dual "· stage ${stage} · ${done_n}/${total}" \
           "$(ts) level=info phase=${phase} event=stage_progress stage=${stage} done=${done_n} total=${total}"
    else
      dual "· stage ${stage} · ${done_n}" \
           "$(ts) level=info phase=${phase} event=stage_progress stage=${stage} done=${done_n}"
    fi
    ;;

  stage-end)
    phase="$1"; stage="$2"; duration="${3:-}"
    if [ -n "${duration}" ]; then
      dual "✓ stage ${stage} · ${duration}s" \
           "$(ts) level=info phase=${phase} event=stage_end stage=${stage} duration_s=${duration}"
    else
      dual "✓ stage ${stage}" \
           "$(ts) level=info phase=${phase} event=stage_end stage=${stage}"
    fi
    ;;

  assumption)
    phase="$1"
    q_p="$(oneline "$2")"; a_p="$(oneline "$3")"
    q_l="$(escape "$2")";  a_l="$(escape "$3")"
    dual "! assumption · Q: ${q_p} · A: ${a_p}" \
         "$(ts) level=info phase=${phase} event=assumption question=\"${q_l}\" answer=\"${a_l}\""
    ;;

  commit)
    sha="$1"
    subj_p="$(oneline "$2")"; subj_l="$(escape "$2")"
    dual "  · commit ${sha:0:7} · ${subj_p}" \
         "$(ts) level=info phase=execute event=commit sha=${sha} subject=\"${subj_l}\""
    ;;

  progress)
    phase="$1"
    msg_p="$(oneline "$2")"; msg_l="$(escape "$2")"
    dual "· ${msg_p}" \
         "$(ts) level=info phase=${phase} event=progress message=\"${msg_l}\""
    ;;

  run-start)
    branch="$1"
    dual "→ /autonomo · run started · branch=${branch}" \
         "$(ts) level=info phase=preflight event=run_start branch=${branch}"
    ;;

  ""|-h|--help|help)
    show_help
    ;;

  *)
    echo "emit.sh: unknown command '${cmd}' — try 'emit.sh --help'" >&2
    exit 2
    ;;
esac
