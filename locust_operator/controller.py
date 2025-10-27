import ast
import random
import time

import kopf
import requests
from constants import GROUP, IN_CLUSTER, LABEL_ANNOTATION_PREFIX, PLURAL, VERSION
from kubernetes import client
from objects import (
    MASTER_P1_PORT_NAME,
    MASTER_P2_PORT_NAME,
    MASTER_WEB_PORT_NAME,
    build_configmap,
    build_master_job,
    build_service,
    build_worker_job,
    ensure,
    exists,
    to_label_selector_string,
)

FORCE_RESTART_FIELDS = {
    ("spec", "image"),
    ("spec", "args"),
    ("spec", "env"),
    ("spec", "master"),
    ("spec", "worker"),
    ("spec", "locustfile"),
}


class LocustTest:
    def __init__(
        self,
        name,
        namespace,
        body: kopf.Body,
        patch: kopf.Patch,
        logger: kopf.Logger,
    ):
        self.name = name
        self.namespace = namespace
        self.spec = body.spec

        self._patch = patch
        self._logger = logger
        self._body = body

        self._core = client.CoreV1Api()
        self._batch = client.BatchV1Api()

    def base_labels(self) -> dict[str, str]:
        return {
            "app.kubernetes.io/name": "locust",
            "app.kubernetes.io/managed-by": "locust-operator",
            "app.kubernetes.io/instance": self.name,
        }

    def get_labels(self, component) -> dict[str, str]:
        return {
            **self.base_labels(),
            **self.specific_labels(component),
            **self.spec.get("labels", {}),
        }

    def get_annotations(self) -> dict[str, str]:
        return {**self.spec.get("annotations", {})}

    def specific_labels(self, component) -> dict[str, str]:
        return {
            f"{LABEL_ANNOTATION_PREFIX}/test-run": self.name,
            f"{LABEL_ANNOTATION_PREFIX}/component": component,
        }

    def reconcile(self, diff: kopf.Diff | None = None):
        restart = False
        if diff:
            restart_fields = [
                path
                for _, path, _, _ in diff
                if path
                and path[0] == "spec"
                and tuple(path[:2]) in FORCE_RESTART_FIELDS
            ]
            self._logger.info(f"Will restart test: {restart_fields} updated!")
            restart = any(restart_fields)

        cm_name = self.ensure_configmap()
        master_svc = self.ensure_master_service()

        # TODO: the user should be able to choose if he wants the webui or not
        self.ensure_webui_service()

        if restart:
            self.delete_jobs()

        try:
            self.ensure_master(cm_name)
            self.ensure_worker(cm_name, master_svc)
        except kopf.TemporaryError:
            self._patch.status["state"] = "RECONCILING"
            raise

        if restart:
            kopf.event(
                self._body,
                type="Normal",
                reason="Restarted",
                message="Locust run restarted due to spec change",
            )

        self._patch.status["state"] = "CREATED"

    def ensure_configmap(self) -> str | None:
        self._logger.debug("Ensuring up configmap")
        locustfile = self.spec.get("locustfile")
        if not locustfile:
            return None

        is_inline = "inline" in locustfile

        if not is_inline:
            existing_cm_name = locustfile.get("configMap", {}).get("name")
            self._logger.debug(f"Already created configmap {existing_cm_name}")
            if not exists(
                lambda: self._core.read_namespaced_config_map(
                    existing_cm_name, self.namespace
                )
            ):
                error_msg = f"Confimap '{existing_cm_name}' does not exist"
                self._patch.status["state"] = "Invalid"
                self._patch.status["message"] = error_msg
                raise kopf.PermanentError(error_msg)

            self._logger.info(f"Found configmap {existing_cm_name}")
            return existing_cm_name

        cm_name = f"{self.name}-locustfile"

        self._logger.debug(f"Creating configmap {cm_name}.")
        cm = build_configmap(
            name=cm_name,
            filename=locustfile.get("inline").get("filename"),
            content=locustfile.get("inline").get("content"),
            labels=self.get_labels("configmap"),
            annotations=self.get_annotations(),
        )

        kopf.adopt(cm)

        ensure(
            lambda cm=cm: self._core.create_namespaced_config_map(self.namespace, cm),
            lambda: self._core.read_namespaced_config_map(cm_name, self.namespace),
            lambda cm=cm: self._core.patch_namespaced_config_map(
                cm_name, self.namespace, cm
            ),
            cm,
        )

        self._logger.info(f"Created configmap {cm_name}")
        return cm_name

    def ensure_master_service(self) -> str:
        self._logger.debug("Ensuring master service")
        name = f"{self.name}-master"

        msvc = build_service(
            name=name,
            labels=self.get_labels("master-service"),
            annotations=self.get_annotations(),
            selector=self.specific_labels("master"),
            # TODO: make type and exposed ports configurable
            type="ClusterIP",
            ports=[
                {
                    "name": MASTER_P1_PORT_NAME,
                    "port": 5557,
                    "target_port": MASTER_P1_PORT_NAME,
                },
                {
                    "name": MASTER_P2_PORT_NAME,
                    "port": 5558,
                    "target_port": MASTER_P2_PORT_NAME,
                },
            ],
        )

        kopf.adopt(msvc)

        ensure(
            lambda svc=msvc: self._core.create_namespaced_service(self.namespace, svc),
            lambda: self._core.read_namespaced_service(name, self.namespace),
            lambda svc=msvc: self._core.patch_namespaced_service(
                name, self.namespace, svc
            ),
            msvc,
        )

        self._logger.info(f"Created master service {name}")
        return name

    def get_webui_service_name(self) -> str:
        return f"{self.name}-webui"

    def ensure_webui_service(self) -> str:
        self._logger.debug("Ensuring webui service")
        name = f"{self.name}-webui"

        msvc = build_service(
            name=name,
            labels=self.get_labels("master-webui"),
            annotations=self.get_annotations(),
            selector=self.specific_labels("master"),
            # TODO: make type and exposed ports configurable
            type="ClusterIP",
            ports=[
                {
                    "name": MASTER_WEB_PORT_NAME,
                    "port": 8089,
                    "target_port": MASTER_WEB_PORT_NAME,
                },
            ],
        )

        kopf.adopt(msvc)

        ensure(
            lambda svc=msvc: self._core.create_namespaced_service(self.namespace, svc),
            lambda: self._core.read_namespaced_service(name, self.namespace),
            lambda svc=msvc: self._core.patch_namespaced_service(
                name, self.namespace, svc
            ),
            msvc,
        )

        self._logger.info(f"Created webui service {name}")
        return name

    def ensure_master(self, cm_name: str | None):
        self._logger.debug("Ensuring locust master job")
        name = f"{self.name}-master"

        pod_spec = self.spec.get("master", {})

        master = build_master_job(
            name=name,
            image=self.spec.get("image", ""),
            args=self.spec.get("args", ""),
            env=self.spec.get("env", []),
            cm_name=cm_name,
            annotations=self.get_annotations(),
            labels=self.get_labels("master"),
            pod_annotations=pod_spec.get("annotations", {}),
            pod_labels={**pod_spec.get("labels", {}), **self.specific_labels("master")},
            pod_resources=pod_spec.get("resources", {}),
            image_pull_policy=self.spec.get("imagePullPolicy"),
            image_pull_secrets=self.spec.get("imagePullSecrets"),
        )

        kopf.adopt(master)

        ensure(
            lambda job=master: self._batch.create_namespaced_job(self.namespace, job),
            lambda: self._batch.read_namespaced_job(name, self.namespace),
            lambda job=master: self._batch.patch_namespaced_job(
                name, self.namespace, job
            ),
            master,
        )

        self._logger.info(f"Created master job {name}")

    def ensure_worker(self, cm_name: str | None, master_svc: str):
        self._logger.debug("Ensuring locust worker job")
        name = f"{self.name}-worker"

        pod_spec = self.spec.get("worker", {})

        worker = build_worker_job(
            name=name,
            image=self.spec.get("image", ""),
            args=self.spec.get("args", ""),
            env=self.spec.get("env", []),
            master_svc=master_svc,
            worker_count=self.spec.get("workers", 1),
            cm_name=cm_name,
            annotations=self.get_annotations(),
            labels=self.get_labels("worker"),
            pod_annotations=pod_spec.get("annotations", {}),
            pod_labels={**pod_spec.get("labels", {}), **self.specific_labels("worker")},
            pod_resources=pod_spec.get("resources", {}),
            image_pull_policy=self.spec.get("imagePullPolicy"),
            image_pull_secrets=self.spec.get("imagePullSecrets"),
        )

        kopf.adopt(worker)

        ensure(
            lambda job=worker: self._batch.create_namespaced_job(self.namespace, job),
            lambda: self._batch.read_namespaced_job(name, self.namespace),
            lambda job=worker: self._batch.patch_namespaced_job(
                name, self.namespace, job
            ),
            worker,
        )

        self._logger.info(f"Created worker job {name}")

    def delete_jobs(self):
        label_selector = to_label_selector_string(self.base_labels())

        jobs = self._batch.list_namespaced_job(
            self.namespace, label_selector=label_selector
        ).items

        if not jobs:
            self._logger.info(f"No Jobs to delete for {self.namespace}/{self.name}.")
            return

        for job in jobs:
            job_name = job.metadata.name
            self._logger.info(f"Deleting Job {self.namespace}/{job_name}")
            self._batch.delete_namespaced_job(
                name=job_name,
                namespace=self.namespace,
                propagation_policy="Foreground",
            )

    async def stats_daemon(self, stopped: kopf.DaemonStopped):
        interval = self.spec.get("metrics", {}).get("intervalSeconds", 5)

        webui_svc_name = self.get_webui_service_name()
        # TODO: Should be configurable and come from centralized place
        # to be shared with master service
        webui_svc_port = 8089

        backoff = 1.0
        while not stopped.is_set():
            t0 = time.time()
            try:
                stats = self.fetch_stats(webui_svc_name, webui_svc_port)

                client.CustomObjectsApi().patch_namespaced_custom_object_status(
                    GROUP,
                    VERSION,
                    self.namespace,
                    PLURAL,
                    self.name,
                    {
                        "status": {
                            "state": stats.get("state", "").upper(),
                            "fail_ratio": f"{int(stats.get('fail_ratio', 0)) * 100}%",
                            "total_rps": int(stats.get("total_rps", 0)),
                            "user_count": int(stats.get("user_count", 0)),
                            "worker_count": int(stats.get("worker_count", 0)),
                            "worker_ratio": f"{stats.get('worker_count', 0)}/{self.spec.get('workers', 1)}",
                        }
                    },
                )

            except Exception as e:
                self._logger.error(f"stats poll error: {e}")
                await stopped.wait(min(backoff, interval))
                backoff = min(backoff * 2.0, 30.0)

            elapsed = time.time() - t0
            base = max(0.0, interval - elapsed)
            jitter = random.uniform(-0.2, 0.2) * interval
            await stopped.wait(max(0.0, base + jitter))

    def fetch_stats(self, svc: str, port: int):
        path = "stats/requests"

        if not IN_CLUSTER:
            raw = str(
                self._core.connect_get_namespaced_service_proxy_with_path(
                    name=f"{svc}:{port}",
                    namespace=self.namespace,
                    path=path,
                )
            )
            return ast.literal_eval(raw)

        else:
            response = requests.get(
                f"http://{svc}.{self.namespace}.svc.cluster.local:{port}/{path}"
            )
            return response.json()
