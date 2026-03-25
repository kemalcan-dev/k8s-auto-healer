# 🔧 k8s-auto-healer

> **Self-healing Kubernetes infrastructure** — detects failures, triggers remediation, and rolls back broken deployments automatically. No pager. No panic. Just reliability.

[![CI/CD](https://github.com/kemalcan-dev/k8s-auto-healer/actions/workflows/ci-cd.yaml/badge.svg)](https://github.com/kemalcan-dev/k8s-auto-healer/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Kubernetes](https://img.shields.io/badge/kubernetes-%23326ce5.svg?style=flat&logo=kubernetes&logoColor=white)](https://kubernetes.io)
[![Prometheus](https://img.shields.io/badge/Prometheus-E6522C?style=flat&logo=Prometheus&logoColor=white)](https://prometheus.io)

---

## 🧠 What is this?

`k8s-auto-healer` is a **production-grade SRE automation framework** that sits inside your Kubernetes cluster and continuously watches for failure signals via Prometheus.

When something breaks, it doesn't just alert — it **acts**.

```
Pod crashes         → auto restart
Memory leak         → pod eviction + restart
CPU spike           → scale up deployment
Bad deploy          → automatic rollback to last stable
DB unreachable      → reconnect attempt + app pod restart
Service down        → Slack/Discord alert + escalation
```

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Kubernetes Cluster                     │
│                                                          │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │Prometheus│───▶│ Alertmanager │───▶│  Auto-Healer  │  │
│  │(scrapes) │    │  (routes)    │    │  (webhook)    │  │
│  └──────────┘    └──────────────┘    └──────┬────────┘  │
│       │                                     │           │
│       │ metrics                             │ K8s API   │
│       ▼                                     ▼           │
│  ┌──────────┐                      ┌────────────────┐   │
│  │  Grafana │                      │  Heal Actions  │   │
│  │(dashbrd) │                      │  ┌──────────┐  │   │
│  └──────────┘                      │  │pod restart│  │   │
│                                    │  │scale up  │  │   │
│  ┌──────────────────────────────┐  │  │rollback  │  │   │
│  │       DB Healer (sidecar)    │  │  │db check  │  │   │
│  │  polls DB every 30s          │  │  └──────────┘  │   │
│  │  restarts app pods on fail   │  └────────────────┘   │
│  └──────────────────────────────┘                       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   Slack / Discord     │
              │   #sre-alerts channel │
              └───────────────────────┘
```

---

## ✨ Features

| Feature | Description | Status |
|---|---|---|
| 🔄 **Pod Auto-Restart** | Crash-looping pods get deleted and rescheduled automatically | ✅ |
| 🧠 **Memory Leak Detection** | Evicts pods consuming >90% of memory limit | ✅ |
| 📈 **CPU Spike Auto-Scale** | Scales deployment replicas when CPU exceeds threshold | ✅ |
| ⏪ **Automatic Rollback** | Reverts to last stable `ReplicaSet` on unhealthy deployments | ✅ |
| 🗄 **DB Health Monitor** | TCP-probes PostgreSQL; restarts app pods if connection lost | ✅ |
| 📣 **Slack Alerts** | Rich notifications on every healing action taken | ✅ |
| 🔐 **RBAC-scoped** | Minimal Kubernetes permissions via dedicated ServiceAccount | ✅ |
| 🚀 **CI/CD Ready** | GitHub Actions pipeline with build, test, validate, deploy | ✅ |

---

## 📁 Project Structure

```
k8s-auto-healer/
├── scripts/
│   └── healers/
│       ├── auto_healer.py        # Alertmanager webhook receiver + action router
│       └── db_healer.py          # DB connectivity monitor
├── k8s/
│   ├── deployments/
│   │   └── auto-healer-deployment.yaml
│   ├── monitoring/
│   │   ├── alert-rules.yaml      # Prometheus alerting rules
│   │   └── alertmanager-config.yaml
│   └── rbac/
│       └── auto-healer-rbac.yaml
├── .github/
│   └── workflows/
│       └── ci-cd.yaml
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites

- Kubernetes cluster (AKS, k3s, or local `kind`)
- `kubectl` configured
- Prometheus + Alertmanager deployed (via `kube-prometheus-stack` Helm chart)

### 1. Deploy the stack

```bash
# Clone the repo
git clone https://github.com/kemalcan-dev/k8s-auto-healer.git
cd k8s-auto-healer

# Create secrets
kubectl create secret generic auto-healer-secrets \
  --from-literal=slack-webhook-url="https://hooks.slack.com/services/XXX" \
  --from-literal=bearer-token="$(openssl rand -hex 32)" \
  -n monitoring

# Apply manifests
kubectl apply -f k8s/rbac/
kubectl apply -f k8s/monitoring/
kubectl apply -f k8s/deployments/

# Verify
kubectl get pods -n monitoring -l app=auto-healer
```

### 2. Register alert rules with Prometheus

```bash
# If using Prometheus Operator (PrometheusRule CRD):
kubectl apply -f k8s/monitoring/alert-rules.yaml

# Verify rules are loaded:
kubectl port-forward svc/prometheus-operated 9090 -n monitoring
# Open: http://localhost:9090/rules
```

### 3. Point Alertmanager to the webhook

Update `alertmanager-config.yaml` with your auto-healer service URL and apply:

```bash
kubectl apply -f k8s/monitoring/alertmanager-config.yaml
```

---

## 🧪 Simulating Failures (Test it!)

```bash
# 1. Simulate a crash-looping pod
kubectl run crasher --image=busybox -- /bin/sh -c "exit 1"

# 2. Simulate memory pressure
kubectl run memhog --image=polinux/stress -- stress --vm 1 --vm-bytes 500M

# 3. Simulate bad deploy (auto-rollback should trigger)
kubectl set image deployment/my-app app=nginx:broken-tag

# 4. Watch healing happen in real time
kubectl logs -f deployment/auto-healer -n monitoring
```

---

## 🔔 Slack Alert Example

```
🚨 [Auto-Healer] PodCrashLooping → action pod_restart — success
   Pod: backend-7d9f8b-xk2p9
   Namespace: production
   Restarts: 6 in last 5 minutes
```

---

## 🛡 Security

- Auto-healer runs as a **non-root user** (UID 1000)
- **Read-only root filesystem**
- Minimal RBAC — only the permissions it actually needs
- Bearer token auth on the webhook endpoint
- Secrets managed via Kubernetes Secrets (use Vault or ESO in production)

---

## 📊 Prometheus Alert Rules Summary

| Alert | Trigger | Action |
|---|---|---|
| `PodCrashLooping` | >1 restart/min for 2m | Delete pod (recreated by controller) |
| `HighMemoryUsage` | >90% memory limit for 3m | Evict and restart pod |
| `CPUSpikeDetected` | >85% CPU limit for 2m | Scale deployment to 3 replicas |
| `DeploymentUnhealthy` | <50% available replicas for 3m | `kubectl rollout undo` |
| `DBConnectionFailed` | `pg_up == 0` for 1m | Restart app pods |
| `ServiceEndpointDown` | 0 available endpoints for 1m | Slack alert + escalation |

---

## 🗺 Roadmap

- [ ] HPA (Horizontal Pod Autoscaler) integration for smarter scaling
- [ ] Runbook automation (auto-execute linked runbooks on alert)
- [ ] Discord webhook support
- [ ] Terraform module for full stack provisioning on AKS
- [ ] Helm chart for easy deployment
- [ ] Multi-cluster support

---

## 🤝 Contributing

PRs welcome. Please open an issue first for major changes.

```bash
# Run tests locally
pip install -r requirements.txt pytest
pytest tests/ -v
```

---

## 📄 License

MIT — see [LICENSE](LICENSE)

---

<p align="center">
  Built by an SRE, for SREs. Because <strong>reliability is a feature</strong>.
</p>
#   k 8 s - a u t o - h e a l e r  
 