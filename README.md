# Locust k8s operator

TODO:
-----

- Support full container environment specification in crd (https://github.com/kubernetes/kubernetes/blob/master/api/openapi-spec/v3/api__v1_openapi.json)
    - env.valueFrom (io.k8s.api.core.v1.EnvVarSource)
    - envFrom (io.k8s.api.core.v1.EnvFromSource)

- Does this makes sense? https://kubernetes.io/docs/tasks/extend-kubernetes/custom-resources/custom-resource-definitions/
    - official k8s spec uses the following in `.env` spec
    ```
    x-kubernetes-list-map-keys: ["name"]
    x-kubernetes-list-type: "map"
    ```

- Handle resource updates, currently we only care about worker counts, all other updates will be reflected in the resource but the stack will not update accordingly

- Error handling in kubernetes apis, should we only handle updates when error?

- Add defaults for resources

- Better information to the user with events/status

- Async stats request