{{/*
Expand the name of the chart.
*/}}
{{- define "robotrader.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "robotrader.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Common labels applied to every object in the chart.
*/}}
{{- define "robotrader.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{ include "robotrader.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels shared by the Deployment pod template and the Service.
*/}}
{{- define "robotrader.selectorLabels" -}}
app.kubernetes.io/name: {{ include "robotrader.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Render MAX_DAILY_LLM_BUDGET_USD as a positive float.

An absent or empty value falls back to 5.0, matching the backend default.
Non-numeric strings coerce to 0 in Sprig, so the `le 0` guard fails closed on
non-numeric, zero, and negative values instead of emitting `%!f(...)`.
*/}}
{{- define "robotrader.maxDailyLlmBudgetUsd" -}}
{{- $raw := .Values.env.maxDailyLlmBudgetUsd -}}
{{- if or (kindIs "invalid" $raw) (and (kindIs "string" $raw) (eq (trim $raw) "")) -}}
5.0
{{- else -}}
{{- $budget := float64 $raw -}}
{{- if le $budget 0.0 -}}
{{- fail "env.maxDailyLlmBudgetUsd must be a positive number" -}}
{{- end -}}
{{- printf "%.1f" $budget -}}
{{- end -}}
{{- end }}
