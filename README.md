```shell
conda create -n lmdeploy-4 python=3.8 -y
conda activate lmdeploy-4
pip install git+https://github.com/AhmedZeer/lmdeploy.git
```

The default prebuilt package is compiled on **CUDA 12** since v0.3.0.
For more information on installing on CUDA 11+ platform, or for instructions on building from source, please refer to the [installation guide](docs/en/get_started/installation.md).

## Offline Batch Inference

```python
import lmdeploy
pipe = lmdeploy.pipeline("internlm/internlm2-chat-7b")
response = pipe(["Hi, pls intro yourself", "Shanghai is"])
print(response)
```
