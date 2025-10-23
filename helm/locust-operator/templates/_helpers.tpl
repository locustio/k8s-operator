{{/*
Expand the name of the chart.
*/}}
{{- define "locust-operator.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "locust-operator.fullname" -}}
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
Create chart name and version as used by the chart label.
*/}}
{{- define "locust-operator.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "locust-operator.labels" -}}
helm.sh/chart: {{ include "locust-operator.chart" . }}
{{ include "locust-operator.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "locust-operator.selectorLabels" -}}
app.kubernetes.io/name: {{ include "locust-operator.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "locust-operator.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "locust-operator.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
RBAC rules for the operator
*/}}
{{- define "locust-operator.rbacRules" -}}
# Framework: runtime observation of namespaces & CRDs (addition/deletion).
- apiGroups: [apiextensions.k8s.io]
  resources: [customresourcedefinitions]
  verbs: [list, watch]
- apiGroups: [""]
  resources: [namespaces]
  verbs: [list, watch]
# Application
- apiGroups: ["locust.cloud"]
  resources: ["*"]
  verbs: ["*"]
# Applcation: Managed resources
- apiGroups: [""]
  resources: ["services", "configmaps"]
  verbs: ["get","create","update","patch","delete"]
- apiGroups: ["batch"]
  resources: ["jobs"]
  verbs: ["get","list","create","update","patch","delete"]
- apiGroups: [""]
  resources: ["events"]
  verbs: ["create", "patch", "update"]
{{- end -}}
