from typing import Dict, List, Tuple
from kubernetes import client


def common_labels(name: str) -> Dict[str, str]:
    return {"app.kubernetes.io/name": "locust", "app.kubernetes.io/managed-by": "locust-operator", "app.kubernetes.io/instance": name}


def cm_name(n):
    return f"{n}-locustfile"


def master_svc_name(n):
    return f"{n}-master"


def web_svc_name(n):
    return f"{n}-web"


def master_dep_name(n):
    return f"{n}-master"


def worker_dep_name(n):
    return f"{n}-worker"


def env_to_k8s(env: List[dict]) -> List[client.V1EnvVar]:
    return [
        client.V1EnvVar(name=e["name"], value=e.get("value", "")) for e in env or []
    ]


def build_configmap(
    namespace: str, name: str, filename: str, content: str, owner_ref
) -> client.V1ConfigMap:
    return client.V1ConfigMap(
        metadata=client.V1ObjectMeta(
            name=cm_name(name),
            namespace=namespace,
            labels=common_labels(name),
            owner_references=[owner_ref],
        ),
        data={filename: content},
    )


def build_services(
    namespace: str,
    name: str,
    service_type: str,
    web_port: int,
    p1: int,
    p2: int,
    owner_ref,
) -> Tuple[client.V1Service, client.V1Service]:
    master = client.V1Service(
        metadata=client.V1ObjectMeta(
            name=master_svc_name(name),
            namespace=namespace,
            labels=common_labels(name),
            owner_references=[owner_ref],
        ),
        spec=client.V1ServiceSpec(
            type="ClusterIP",
            selector={**common_labels(name), "role": "master"},
            ports=[
                client.V1ServicePort(name="comm1", port=p1, target_port=p1),
                client.V1ServicePort(name="comm2", port=p2, target_port=p2),
            ],
        ),
    )
    web = client.V1Service(
        metadata=client.V1ObjectMeta(
            name=web_svc_name(name),
            namespace=namespace,
            labels=common_labels(name),
            owner_references=[owner_ref],
        ),
        spec=client.V1ServiceSpec(
            type=service_type,
            selector={**common_labels(name), "role": "master"},
            ports=[
                client.V1ServicePort(name="web", port=web_port, target_port=web_port)
            ],
        ),
    )
    return master, web


def build_master_deployment(
    namespace: str,
    name: str,
    image: str,
    has_cm: bool,
    filename: str,
    host: str,
    web_port: int,
    p1: int,
    p2: int,
    extra_args: list,
    env: list,
    resources: dict,
    owner_ref,
):
    vols = []
    vms = []
    args = ["-f", f"/mnt/locust/{filename}", "--master", f"--web-port={web_port}"]
    if host:
        args += ["--host", host]
    if extra_args:
        args += extra_args

    if has_cm:
        vols.append(
            client.V1Volume(
                name="locustfile",
                config_map=client.V1ConfigMapVolumeSource(name=cm_name(name)),
            )
        )
    else:
        vols.append(
            client.V1Volume(
                name="locustfile", empty_dir=client.V1EmptyDirVolumeSource()
            )
        )
    vms.append(client.V1VolumeMount(name="locustfile", mount_path="/mnt/locust"))

    container = client.V1Container(
        name="master",
        image=image,
        args=args,
        ports=[
            client.V1ContainerPort(container_port=web_port, name="web"),
            client.V1ContainerPort(container_port=p1, name="comm1"),
            client.V1ContainerPort(container_port=p2, name="comm2"),
        ],
        env=env_to_k8s(env),
        volume_mounts=vms,
        resources=(resources or {}).get("master"),
    )
    return client.V1Deployment(
        metadata=client.V1ObjectMeta(
            name=master_dep_name(name),
            namespace=namespace,
            labels=common_labels(name),
            owner_references=[owner_ref],
        ),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(
                match_labels={**common_labels(name), "role": "master"}
            ),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    labels={**common_labels(name), "role": "master"}
                ),
                spec=client.V1PodSpec(containers=[container], volumes=vols),
            ),
        ),
    )


def build_worker_deployment(
    namespace: str,
    name: str,
    image: str,
    has_cm: bool,
    filename: str,
    replicas: int,
    master_host: str,
    env: list,
    resources: dict,
    owner_ref,
):
    vols = []
    vms = []
    args = ["-f", f"/mnt/locust/{filename}", "--worker", f"--master-host={master_host}"]
    if has_cm:
        vols.append(
            client.V1Volume(
                name="locustfile",
                config_map=client.V1ConfigMapVolumeSource(name=cm_name(name)),
            )
        )
    else:
        vols.append(
            client.V1Volume(
                name="locustfile", empty_dir=client.V1EmptyDirVolumeSource()
            )
        )
    vms.append(client.V1VolumeMount(name="locustfile", mount_path="/mnt/locust"))

    container = client.V1Container(
        name="worker",
        image=image,
        args=args,
        env=env_to_k8s(env),
        volume_mounts=vms,
        resources=(resources or {}).get("worker"),
    )
    return client.V1Deployment(
        metadata=client.V1ObjectMeta(
            name=worker_dep_name(name),
            namespace=namespace,
            labels=common_labels(name),
            owner_references=[owner_ref],
        ),
        spec=client.V1DeploymentSpec(
            replicas=replicas,
            selector=client.V1LabelSelector(
                match_labels={**common_labels(name), "role": "worker"}
            ),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    labels={**common_labels(name), "role": "worker"}
                ),
                spec=client.V1PodSpec(containers=[container], volumes=vols),
            ),
        ),
    )
