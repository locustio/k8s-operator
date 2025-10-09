import logging
import os

import kopf
from kubernetes import config

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
