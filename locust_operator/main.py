import datetime
import logging

import kopf
from constants import IN_CLUSTER, LABEL_ANNOTATION_PREFIX, LOCUST_TEST_RESOURCE
from controller import LocustTest
from kubernetes import client, config

try:
    if IN_CLUSTER:
        config.load_incluster_config()
    else:
        config.load_kube_config()
except config.config_exception.ConfigException:
    raise Exception("Unable to configure kubernetes client!")


core_api = client.CoreV1Api()


@kopf.on.startup()
def on_startup(settings: kopf.OperatorSettings, logger: kopf.Logger, **_):
    logger.info("Starting Locust Operator.")

    settings.watching.server_timeout = 120
    settings.watching.client_timeout = 150
    settings.watching.connect_timeout = 5

    settings.networking.request_timeout = 10

    # Kopf posts all logger messages as events as well, we want to limit it
    # So we only post the highest level possible, we could disable posting
    # entirely but then kopf.event() would also not post anything.
    # https://github.com/nolar/kopf/issues/1186
    settings.posting.enabled = True
    settings.posting.level = logging.CRITICAL

    settings.posting.reporting_component = "locust-operator"
    settings.posting.event_name_prefix = "locust-event"

    settings.persistence.finalizer = f"{LABEL_ANNOTATION_PREFIX}/kopf-finalizer"
    settings.persistence.progress_storage = kopf.AnnotationsProgressStorage(
        prefix=LABEL_ANNOTATION_PREFIX
    )
    settings.persistence.diffbase_storage = kopf.AnnotationsDiffBaseStorage(
        prefix=LABEL_ANNOTATION_PREFIX
    )


@kopf.on.probe(id="now")
def get_current_timestamp(logger: kopf.Logger, **_) -> str:
    logger.debug("on_probe")
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


@kopf.on.create(LOCUST_TEST_RESOURCE)
def on_create(
    name, namespace, patch: kopf.Patch, spec: kopf.Body, logger: kopf.Logger, **_
):
    logger.info(f"Initializing LocustTest name={name} namespace={namespace}")

    locust_test = LocustTest(name, namespace, spec, patch, logger)
    locust_test.reconcile()


@kopf.on.field(LOCUST_TEST_RESOURCE, field="spec.workers", old=kopf.PRESENT)
def update_worker_count(old, new, body, logger: kopf.Logger, **_):
    logger.info(f"Updating worker count {old} -> {new}")

    # TODO: patch workers

    kopf.event(
        body,
        type="Normal",
        reason="Scaled",
        message=f"Updated worker count ({old} -> {new})",
    )


@kopf.daemon(LOCUST_TEST_RESOURCE, initial_delay=5.0)
async def stats_daemon(
    name,
    namespace,
    patch: kopf.Patch,
    spec: kopf.Body,
    logger: kopf.Logger,
    stopped: kopf.DaemonStopped,
    **_,
):
    logger.debug(f"Updating LocustTest name={name} namespace={namespace} status")

    locust_test = LocustTest(name, namespace, spec, patch, logger)
    await locust_test.stats_daemon(stopped)
