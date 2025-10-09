from kubernetes import client

from constants import FINALIZER, GROUP, PLURAL, VERSION
from k8s import build_configmap, build_master_deployment, build_services, build_worker_deployment, cm_name, master_dep_name, master_svc_name, web_svc_name, worker_dep_name
from models import LocustTestSpec, LocustTestStatus


class LocustTest:
    def __init__(self, namespace: str, name: str, body: dict):
        self.ns = namespace
        self.name = name
        self.body = body

        self.core = client.CoreV1Api()
        self.apps = client.AppsV1Api()
        self.custom = client.CustomObjectsApi()

    def _owner_ref(self) -> client.V1OwnerReference:
        meta = self.body["metadata"]
        return client.V1OwnerReference(
            api_version=f"{GROUP}/{VERSION}", kind="LocustTest",
            name=meta["name"], uid=meta["uid"], controller=True, block_owner_deletion=True
        )

    def _ensure(self, create, read, patch, desired):
        try:
            read()
            return patch(desired)
        except client.exceptions.ApiException as e:
            if e.status == 404:
                return create(desired)
            raise

    # def _set_status(self, status: LocustTestStatus):
    #     body = {"status": status}
    #     self.custom.patch_namespaced_custom_object_status(GROUP, VERSION, self.ns, PLURAL, self.name, body)

    def reconcile(self):
        spec = LocustTestSpec.model_validate(self.body.get("spec", {}))

        # Finalizer (idempotent)
        # fins = self.body["metadata"].get("finalizers", [])
        # if FINALIZER not in fins:
        #     self.custom.patch_namespaced_custom_object(
        #         GROUP, VERSION, self.ns, PLURAL, self.name,
        #         {"metadata": {"finalizers": [*fins, FINALIZER]}}
        #     )

        ow = self._owner_ref()
        has_cm = bool(spec.locustfile and spec.locustfile.content)
        filename = spec.locustfile.filename if spec.locustfile else "locustfile.py"
        image = spec.image
        worker_image = spec.workerImage or spec.image

        # Optional CM for inline locustfile
        if has_cm:
            cm = build_configmap(self.ns, self.name, filename, spec.locustfile.content, ow)
            self._ensure(
                lambda b=cm: self.core.create_namespaced_config_map(self.ns, b),
                lambda: self.core.read_namespaced_config_map(cm_name(self.name), self.ns),
                lambda b=cm: self.core.patch_namespaced_config_map(cm_name(self.name), self.ns, b),
                cm
            )

        # Services
        msvc, wsvc = build_services(self.ns, self.name, spec.service.type, spec.webPort,
                                             spec.masterPorts.p1, spec.masterPorts.p2, ow)
        self._ensure(lambda b=msvc: self.core.create_namespaced_service(self.ns, b),
                     lambda: self.core.read_namespaced_service(master_svc_name(self.name), self.ns),
                     lambda b=msvc: self.core.patch_namespaced_service(master_svc_name(self.name), self.ns, b),
                     msvc)
        self._ensure(lambda b=wsvc: self.core.create_namespaced_service(self.ns, b),
                     lambda: self.core.read_namespaced_service(web_svc_name(self.name), self.ns),
                     lambda b=wsvc: self.core.patch_namespaced_service(web_svc_name(self.name), self.ns, b),
                     wsvc)

        # Master & Workers
        master_dep = build_master_deployment(
            self.ns, self.name, image, has_cm, filename, spec.host or "",
            spec.webPort, spec.masterPorts.p1, spec.masterPorts.p2,
            spec.extraArgs, [e.model_dump() for e in spec.env], (spec.resources or {}).model_dump() if spec.resources else {}, ow
        )
        worker_dep = build_worker_deployment(
            self.ns, self.name, worker_image, has_cm, filename, spec.workers,
            master_svc_name(self.name), [e.model_dump() for e in spec.env],
            (spec.resources or {}).model_dump() if spec.resources else {}, ow
        )

        self._ensure(lambda b=master_dep: self.apps.create_namespaced_deployment(self.ns, b),
                     lambda: self.apps.read_namespaced_deployment(master_dep_name(self.name), self.ns),
                     lambda b=master_dep: self.apps.patch_namespaced_deployment(master_dep_name(self.name), self.ns, b),
                     master_dep)

        self._ensure(lambda b=worker_dep: self.apps.create_namespaced_deployment(self.ns, b),
                     lambda: self.apps.read_namespaced_deployment(worker_dep_name(self.name), self.ns),
                     lambda b=worker_dep: self.apps.patch_namespaced_deployment(worker_dep_name(self.name), self.ns, b),
                     worker_dep)

        # self._set_status(LocustTestStatus(phase="Running", masterService=web_svc_name(self.name),
        #                                   message="Master & workers created"))

    def finalize(self):
        fins = [f for f in self.body["metadata"].get("finalizers", []) if f != FINALIZER]
        # if len(fins) != len(self.body["metadata"].get("finalizers", [])):
        #     self.custom.patch_namespaced_custom_object(GROUP, VERSION, self.ns, PLURAL, self.name,
        #                                                     {"metadata": {"finalizers": fins}})
    