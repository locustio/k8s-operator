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

- Only read() in ensure to be nice to the kubernetes api

- If we retry `on_update` because we are waiting for jobs to terminate we should skip ensuring all the other components (for each we always make 2 api requests - read/patch)

- Add defaults for resources

- Listen to external configmap changes

- Async stats request

- Helm

- A lot of testing!

- Add operator configurations