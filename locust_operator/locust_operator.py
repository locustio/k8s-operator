import logging
import os

import kopf
from consts import FINALIZER, GROUP, PLURAL, VERSION
from kubernetes import client, config
from kubernetes.client import V1OwnerReference

try:
    # Allow running inside or outside cluster
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        config.load_incluster_config()
    else:
        config.load_kube_config()
except config.config_exception.ConfigException:
    raise Exception("Unable to configure kubernetes client!")


def labels(name):
    return {"app.kubernetes.io/name": "locust", "app.kubernetes.io/instance": name}


def build_configmap(namespace, name, filename, content):
    return client.V1ConfigMap(
        metadata=client.V1ObjectMeta(
            name=f"{name}-locustfile", namespace=namespace, labels=labels(name)
        ),
        data={filename: content},
    )


def build_services(namespace, name, service_type, web_port, p1, p2):
    master = client.V1Service(
        metadata=client.V1ObjectMeta(
            name=f"{name}-master", namespace=namespace, labels=labels(name)
        ),
        spec=client.V1ServiceSpec(
            type="ClusterIP",
            selector=dict(labels(name), **{"role": "master"}),
            ports=[
                client.V1ServicePort(name="port1", port=p1, target_port=p1),
                client.V1ServicePort(name="port2", port=p2, target_port=p2),
            ],
        ),
    )
    # Web UI service
    web = client.V1Service(
        metadata=client.V1ObjectMeta(
            name=f"{name}-web", namespace=namespace, labels=labels(name)
        ),
        spec=client.V1ServiceSpec(
            type=service_type,
            selector=dict(labels(name), **{"role": "master"}),
            ports=[
                client.V1ServicePort(name="web", port=web_port, target_port=web_port)
            ],
        ),
    )
    return master, web


def owner_ref(body) -> V1OwnerReference:
    meta = body["metadata"]
    return V1OwnerReference(
        api_version=f"{GROUP}/{VERSION}",
        kind="LocustTest",
        name=meta["name"],
        uid=meta["uid"],
        controller=True,
        block_owner_deletion=True,
    )


@kopf.on.startup()
def on_startup(settings: kopf.OperatorSettings, **_):
    print("on_startup")
    # TODO: configure operator settings
    settings.posting.level = (
        logging.INFO if (os.getenv("DEBUG") is None) else logging.DEBUG
    )


@kopf.on.cleanup()
def on_cleanup(*args, **kwargs):
    print("on_cleanup")


@kopf.on.create(GROUP, VERSION, PLURAL)
def create(body, spec, meta, namespace, **_):
    name = meta["name"]

    config = {
        "image": spec.get("image", "locustio/locust:latest"),
        "worker_image": spec.get(
            "workerImage", spec.get("image", "locustio/locust:latest")
        ),
        "workers": int(spec.get("workers", 1)),
        "host": spec.get("host"),
        "extra_args": spec.get("extraArgs") or [],
        "env": spec.get("env") or [],
        "resources": spec.get("resources") or {},
    }
    print(config)
    web_port = int(spec.get("webPort", 8089))
    mp = spec.get("masterPorts") or {}
    p1, p2 = int(mp.get("p1", 5557)), int(mp.get("p2", 5558))
    service_type = (spec.get("service") or {}).get("type", "ClusterIP")

    locustfile_spec = spec.get("locustfile")
    has_cm = bool(locustfile_spec and locustfile_spec.get("content"))
    filename = (locustfile_spec or {}).get("filename", "locustfile.py")

    api = client.CoreV1Api()

    if has_cm:
        print("Creating config map!")
        cm = build_configmap(namespace, name, filename, locustfile_spec["content"])
        api.create_namespaced_config_map(namespace, cm)
        print("CM created")

    print("Building services")
    master_svc, web_svc = build_services(
        namespace, name, service_type, web_port, p1, p2
    )
    print("creating master svc")
    api.create_namespaced_service(namespace, master_svc)
    print("creating web svc")
    api.create_namespaced_service(namespace, web_svc)
    print("svc done")


@kopf.on.delete(GROUP, VERSION, PLURAL)
def delete(body, meta, namespace, logger, **_):
    name = meta["name"]

    fins = [f for f in meta.get("finalizers", []) if f != FINALIZER]
    client.CustomObjectsApi().patch_namespaced_custom_object(
        GROUP, VERSION, namespace, PLURAL, name, {"metadata": {"finalizers": fins}}
    )
    logger.info(f"LocustTest {name} finalized")

