#!/usr/bin/env python3
"""
K8s Auto-Healer - Core Healing Orchestrator
Listens to Alertmanager webhooks and triggers appropriate healing actions.
"""

import os
import json
import logging
import subprocess
from datetime import datetime
from flask import Flask, request, jsonify
from kubernetes import client, config
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
log = logging.getLogger("auto-healer")

app = Flask(__name__)

# Load k8s config (in-cluster or local kubeconfig)
try:
    config.load_incluster_config()
    log.info("Loaded in-cluster k8s config")
except config.ConfigException:
    config.load_kube_config()
    log.info("Loaded local kubeconfig")

v1 = client.CoreV1Api()
apps_v1 = client.AppsV1Api()

SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")
NAMESPACE = os.getenv("HEAL_NAMESPACE", "default")


# ──────────────────────────────────────────────
# Healing Actions
# ──────────────────────────────────────────────

def restart_pod(pod_name: str, namespace: str) -> dict:
    """Delete a crashing pod so its owner (Deployment/ReplicaSet) recreates it."""
    try:
        v1.delete_namespaced_pod(name=pod_name, namespace=namespace)
        log.info(f"[HEAL] Deleted pod {pod_name} in {namespace} → will be recreated")
        return {"action": "pod_restart", "pod": pod_name, "status": "success"}
    except client.exceptions.ApiException as e:
        log.error(f"[HEAL] Failed to delete pod {pod_name}: {e}")
        return {"action": "pod_restart", "pod": pod_name, "status": "error", "detail": str(e)}


def scale_deployment(deployment: str, namespace: str, replicas: int) -> dict:
    """Scale a deployment up or down."""
    try:
        body = {"spec": {"replicas": replicas}}
        apps_v1.patch_namespaced_deployment_scale(
            name=deployment, namespace=namespace, body=body
        )
        log.info(f"[HEAL] Scaled {deployment} to {replicas} replicas")
        return {"action": "scale", "deployment": deployment, "replicas": replicas, "status": "success"}
    except client.exceptions.ApiException as e:
        log.error(f"[HEAL] Scale failed for {deployment}: {e}")
        return {"action": "scale", "deployment": deployment, "status": "error", "detail": str(e)}


def rollback_deployment(deployment: str, namespace: str) -> dict:
    """Roll back a deployment to its previous revision."""
    try:
        result = subprocess.run(
            ["kubectl", "rollout", "undo", f"deployment/{deployment}", "-n", namespace],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            log.info(f"[HEAL] Rolled back {deployment}: {result.stdout.strip()}")
            return {"action": "rollback", "deployment": deployment, "status": "success"}
        else:
            log.error(f"[HEAL] Rollback failed: {result.stderr}")
            return {"action": "rollback", "deployment": deployment, "status": "error", "detail": result.stderr}
    except subprocess.TimeoutExpired:
        return {"action": "rollback", "deployment": deployment, "status": "error", "detail": "timeout"}


def check_db_connectivity(db_host: str, db_port: int = 5432) -> bool:
    """Quick TCP probe to check DB reachability."""
    import socket
    try:
        with socket.create_connection((db_host, db_port), timeout=5):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


# ──────────────────────────────────────────────
# Alert Router
# ──────────────────────────────────────────────

ALERT_HANDLERS = {
    "PodCrashLooping":      lambda a: restart_pod(a["labels"].get("pod", ""), a["labels"].get("namespace", NAMESPACE)),
    "HighMemoryUsage":      lambda a: restart_pod(a["labels"].get("pod", ""), a["labels"].get("namespace", NAMESPACE)),
    "CPUSpikeDetected":     lambda a: scale_deployment(a["labels"].get("deployment", ""), a["labels"].get("namespace", NAMESPACE), replicas=3),
    "DeploymentUnhealthy":  lambda a: rollback_deployment(a["labels"].get("deployment", ""), a["labels"].get("namespace", NAMESPACE)),
    "DBConnectionFailed":   lambda a: {"action": "db_check", "reachable": check_db_connectivity(a["labels"].get("db_host", "localhost"))},
}


def notify_slack(alert_name: str, result: dict):
    if not SLACK_WEBHOOK:
        return
    icon = "✅" if result.get("status") == "success" else "❌"
    payload = {
        "text": f"{icon} *[Auto-Healer]* `{alert_name}` → action `{result.get('action')}` — {result.get('status', 'unknown')}"
    }
    try:
        requests.post(SLACK_WEBHOOK, json=payload, timeout=5)
    except Exception as e:
        log.warning(f"Slack notify failed: {e}")


# ──────────────────────────────────────────────
# Webhook Endpoint
# ──────────────────────────────────────────────

@app.route("/webhook", methods=["POST"])
def alertmanager_webhook():
    payload = request.get_json(force=True)
    if not payload:
        return jsonify({"error": "empty payload"}), 400

    results = []
    for alert in payload.get("alerts", []):
        alert_name = alert["labels"].get("alertname", "unknown")
        status = alert.get("status", "firing")

        if status != "firing":
            log.info(f"[SKIP] Alert {alert_name} is {status}, no action needed")
            continue

        handler = ALERT_HANDLERS.get(alert_name)
        if handler:
            log.info(f"[ROUTE] Handling alert: {alert_name}")
            result = handler(alert)
            notify_slack(alert_name, result)
            results.append({alert_name: result})
        else:
            log.warning(f"[SKIP] No handler for alert: {alert_name}")
            results.append({alert_name: "no_handler"})

    return jsonify({"processed": len(results), "results": results})


@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
