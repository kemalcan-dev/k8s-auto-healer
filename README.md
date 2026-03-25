# 🔧 k8s-auto-healer

> **Self-healing Kubernetes infrastructure** — detects failures, triggers remediation, and rolls back broken deployments automatically. No pager. No panic. Just reliability.

[![CI/CD](https://github.com/kemalcan-dev/k8s-auto-healer/actions/workflows/ci-cd.yaml/badge.svg)](https://github.com/kemalcan-dev/k8s-auto-healer/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Kubernetes](https://img.shields.io/badge/kubernetes-%23326ce5.svg?style=flat&logo=kubernetes&logoColor=white)](https://kubernetes.io)
[![Prometheus](https://img.shields.io/badge/Prometheus-E6522C?style=flat&logo=Prometheus&logoColor=white)](https://prometheus.io)
[![Python](https://img.shields.io/badge/python-3670A0?style=flat&logo=python&logoColor=ffdd54)](https://www.python.org)

---

## 🧠 What is this?

`k8s-auto-healer` is a **production-grade SRE automation framework** that sits inside your Kubernetes cluster and continuously watches for failure signals via Prometheus.

When something breaks, it doesn't just alert — it **acts**.

| Problem | Solution |
|---------|----------|
| Pod crashes | 🔄 Auto restart |
| Memory leak | 🧠 Pod eviction + restart |
| CPU spike | 📈 Scale up deployment |
| Bad deploy | ⏪ Automatic rollback to last stable |
| DB unreachable | 🗄 Reconnect attempt + app pod restart |
| Service down | 📣 Slack/Discord alert + escalation |

---

## 🏗 Architecture

```mermaid
graph TB
    subgraph "Kubernetes Cluster"
        P[Prometheus<br/>scrapes metrics] --> A[Alertmanager<br/>routes alerts]
        A --> H[Auto-Healer<br/>webhook receiver]
        H --> K[K8s API]
        H --> HA[Heal Actions]
        
        HA --> PR[pod restart]
        HA --> SU[scale up]
        HA --> RB[rollback]
        
        DB[DB Healer<br/>sidecar container] --> DC[db check]
        DC --> APP[restart app pods]
        
        G[Grafana<br/>dashboard] --> P
    end
    
    H --> S[Slack / Discord<br/>#sre-alerts]
