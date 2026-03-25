#!/usr/bin/env python3
"""
DB Connection Health Monitor
Continuously checks DB connectivity; triggers pod restart if connection pool is exhausted.
"""

import os
import sys
import time
import logging
import psycopg2
from kubernetes import client, config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("db-healer")

DB_HOST     = os.getenv("DB_HOST", "postgres-svc")
DB_PORT     = int(os.getenv("DB_PORT", "5432"))
DB_NAME     = os.getenv("DB_NAME", "appdb")
DB_USER     = os.getenv("DB_USER", "app")
DB_PASS     = os.getenv("DB_PASS", "")
NAMESPACE   = os.getenv("NAMESPACE", "default")
APP_LABEL   = os.getenv("APP_LABEL", "app=backend")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
INTERVAL    = int(os.getenv("CHECK_INTERVAL", "30"))


def get_k8s_client():
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.CoreV1Api()


def check_db() -> bool:
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT,
            dbname=DB_NAME, user=DB_USER, password=DB_PASS,
            connect_timeout=5
        )
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.close()
        return True
    except psycopg2.OperationalError as e:
        log.warning(f"DB check failed: {e}")
        return False


def restart_app_pods(v1: client.CoreV1Api):
    """Find pods matching APP_LABEL and delete them (Deployment recreates them)."""
    label_selector = APP_LABEL
    pods = v1.list_namespaced_pod(namespace=NAMESPACE, label_selector=label_selector)
    if not pods.items:
        log.warning(f"No pods found with label '{label_selector}' in {NAMESPACE}")
        return

    for pod in pods.items:
        pod_name = pod.metadata.name
        log.info(f"[HEAL] Restarting pod {pod_name} due to DB connection failure")
        try:
            v1.delete_namespaced_pod(name=pod_name, namespace=NAMESPACE)
        except client.exceptions.ApiException as e:
            log.error(f"Failed to delete pod {pod_name}: {e}")


def main():
    v1 = get_k8s_client()
    failures = 0
    log.info(f"Starting DB health monitor → {DB_HOST}:{DB_PORT}/{DB_NAME} (interval={INTERVAL}s)")

    while True:
        if check_db():
            log.info(f"[OK] DB connection healthy")
            failures = 0
        else:
            failures += 1
            log.warning(f"[WARN] DB failure count: {failures}/{MAX_RETRIES}")

            if failures >= MAX_RETRIES:
                log.error("[HEAL] Max retries reached → restarting app pods")
                restart_app_pods(v1)
                failures = 0  # reset after action

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
