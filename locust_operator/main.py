import json
import logging
import os
import random
import time

import kopf
from kubernetes import config, client
import requests

from constants import GROUP, PLURAL, VERSION
from controller import LocustTest


@kopf.on.startup()
def _startup(settings: kopf.OperatorSettings, **_):
    print("on_startup")

    # TODO: ---- TESTS ----
    settings.peering.standalone = True
    settings.watching.server_timeout = 30
    settings.watching.client_timeout = 35

    settings.posting.level = (
        logging.INFO if (os.getenv("DEBUG") is None) else logging.DEBUG
    )
    # ---------------

    try:
        if os.getenv("KUBERNETES_SERVICE_HOST"):
            config.load_incluster_config()
        else:
            config.load_kube_config()
    except config.config_exception.ConfigException:
        raise Exception("Unable to configure kubernetes client!")


@kopf.on.create(GROUP, VERSION, PLURAL)
def on_create(body, meta, namespace, **_):
    r = LocustTest(namespace, meta["name"], body)
    r.reconcile()


@kopf.on.update(GROUP, VERSION, PLURAL)
def on_update(body, meta, namespace, **_):
    r = LocustTest(namespace, meta["name"], body)
    r.reconcile()


@kopf.on.delete(GROUP, VERSION, PLURAL)
def on_delete(body, meta, namespace, **_):
    r = LocustTest(namespace, meta["name"], body)
    r.finalize()


@kopf.daemon(GROUP, VERSION, PLURAL, initial_delay=5.0)
def stats_daemon(spec, name, namespace, stopped, **_):
    interval = float(spec.get("metrics", {}).get("intervalSeconds", 5))
    web_port = int(spec.get("webPort", 8089))

    # url = f"http://{name}-web.{namespace}.svc.cluster.local:{web_port}/stats/requests"
    def _make_request():
        svc = f"{name}-web:{web_port}"
        path = "stats/requests"

        raw = client.CoreV1Api().connect_get_namespaced_service_proxy_with_path(
            name=svc,
            namespace=namespace,
            path=path,
        )
        # FIXME: Very unsafe
        return eval(raw)
    
    backoff = 1.0
    while not stopped.is_set():
        t0 = time.time()
        try:
            resp = _make_request()
            print(f"""
    state: {resp["state"]}
    fail_ratio: {resp["fail_ratio"]}
    total_rps: {resp["total_rps"]}
    user_count: {resp["user_count"]}
    worker_count: {resp["worker_count"]}
""")
            # if resp.ok:
            #     data = resp.json() or {}
            #     print(f"[{namespace}/{name}] polled {data}")
            #     backoff = 1.0
            # else:
            #     print(f"[{namespace}/{name}] HTTP {resp.status_code} from {url}")
        except Exception as e:
            print(f"[{namespace}/{name}] poll error: {e}")
            stopped.wait(min(backoff, interval))
            backoff = min(backoff * 2.0, 30.0)

        elapsed = time.time() - t0
        base = max(0.0, interval - elapsed)
        jitter = random.uniform(-0.2, 0.2) * interval
        stopped.wait(max(0.0, base + jitter))