# Copyright (c) OpenMMLab. All rights reserved.
from logging import Logger
from typing import List

from lmdeploy.utils import get_logger


def _handle_exception(e: Exception,
                      mod_name: str,
                      logger: Logger,
                      message: str = None):
    red_color = '\033[31m'
    reset_color = '\033[0m'
    if message is None:
        message = 'Please ensure it has been installed correctly.'
    logger.debug('Exception', exc_info=1)
    logger.error(f'{type(e).__name__}: {e}')
    logger.error(f'{red_color}'
                 f'<{mod_name}> test failed!\n'
                 f'{message}'
                 f'{reset_color}')
    exit(1)


def check_env_deeplink(device_type: str):
    """check Deeplink environment."""
    try_import_deeplink(device_type)


def try_import_deeplink(device_type: str):
    """import dlinfer if specific device_type is set."""
    deeplink_device_type_list = [
        'ascend',
        'npu',
        'maca',
    ]
    if device_type in deeplink_device_type_list:
        logger = get_logger('lmdeploy')
        try:
            import dlinfer.framework.lmdeploy_ext  # noqa: F401
        except Exception as e:
            _handle_exception(e, 'PyTorch', logger)


def check_env_torch():
    """check PyTorch environment."""
    logger = get_logger('lmdeploy')

    try:
        logger.debug('Checking <PyTorch> environment.')
        import torch

        a = torch.tensor([1, 2], device='cuda')
        b = a.new_tensor([3, 4], device='cuda')
        c = a + b
        torch.testing.assert_close(c, a.new_tensor([4, 6]))
    except Exception as e:
        _handle_exception(e, 'PyTorch', logger)


MAX_TRITON_VERSION = '3.0.0'


def check_env_triton(device: str):
    """check OpenAI Triton environment."""
    from packaging import version
    logger = get_logger('lmdeploy')

    msg = (
        'Please ensure that your device is functioning properly with <Triton>.\n'  # noqa: E501
        'You can verify your environment by running '
        '`python -m lmdeploy.pytorch.check_env.triton_custom_add`.')
    try:
        logger.debug('Checking <Triton> environment.')
        import torch
        import triton
        triton_version = version.parse(triton.__version__)
        if triton_version > version.parse(MAX_TRITON_VERSION):
            logger.warning(
                f'Engine has not been tested on triton>{MAX_TRITON_VERSION}.')

        from .triton_custom_add import custom_add
        a = torch.tensor([1, 2], device='cuda')
        b = a.new_tensor([3, 4], device='cuda')
        c = custom_add(a, b)
        torch.testing.assert_close(c, a + b)
    except RuntimeError as e:
        ptxas_error = 'device kernel image is invalid'
        if len(e.args) > 0 and ptxas_error in e.args[0]:
            msg = (
                'This Error might caused by mismatching between NVIDIA Driver and nvcc compiler. \n'  # noqa: E501
                'Try solution https://github.com/triton-lang/triton/issues/1955#issuecomment-1929908209'  # noqa: E501
                ' or reinstall the driver.')
        _handle_exception(e, 'Triton', logger, msg)
    except Exception as e:
        _handle_exception(e, 'Triton', logger, msg)

    if device == 'cuda':
        device_cap = torch.cuda.get_device_capability()
        TRITON_VER_231 = version.parse('2.3.1')

        if device_cap[0] <= 7:
            if triton_version <= TRITON_VER_231:
                err = RuntimeError(
                    'Attention triton kernel does not fully support '
                    'triton<3.0.0 on device with capability<8. '
                    'Please upgrade your triton version.')
                _handle_exception(err, 'Triton', logger)


def check_env(device_type: str):
    """check all environment."""
    logger = get_logger('lmdeploy')
    logger.info('Checking environment for PyTorch Engine.')
    check_env_deeplink(device_type)
    check_env_torch()
    if device_type == 'cuda':
        check_env_triton('cuda')


MIN_TRANSFORMERS_VERSION = '4.33.0'
MAX_TRANSFORMERS_VERSION = '4.44.1'


def check_awq(hf_config, device_type):
    """check awq support."""
    logger = get_logger('lmdeploy')
    if device_type == 'cuda':
        quantization_config = getattr(hf_config, 'quantization_config', dict())
        quant_method = quantization_config.get('quant_method', None)
        if quant_method != 'awq':
            return
        try:
            import awq  # noqa
        except Exception as e:
            _handle_exception(e, 'autoawq', logger)

        try:
            import awq_ext  # noqa
        except Exception:
            logger.debug('Exception:', exc_info=1)
            logger.warning('Failed to import `awq_ext`. '
                           'Try reinstall it from source: '
                           'https://github.com/casper-hansen/AutoAWQ_kernels')


def check_transformers_version(model_path: str,
                               trust_remote_code: bool = True,
                               dtype: str = 'auto',
                               device_type: str = 'cuda'):
    """check transformers version."""
    from packaging import version
    logger = get_logger('lmdeploy')

    def __check_transformers_version():
        """check transformers version."""
        logger.debug('Checking <transformers> version.')
        trans_version = None
        try:
            import transformers
            trans_version = version.parse(transformers.__version__)
            min_version = version.parse(MIN_TRANSFORMERS_VERSION)
            max_version = version.parse(MAX_TRANSFORMERS_VERSION)
            if trans_version < min_version or trans_version > max_version:
                logger.warning('LMDeploy requires transformers version: '
                               f'[{MIN_TRANSFORMERS_VERSION} ~ '
                               f'{MAX_TRANSFORMERS_VERSION}], '
                               'but found version: '
                               f'{transformers.__version__}')
        except Exception as e:
            _handle_exception(e, 'transformers', logger)
        return transformers, trans_version

    def __check_config(trans_version):
        """check config."""
        logger.debug('Checking <Model> AutoConfig.from_pretrained.')
        try:
            from transformers import AutoConfig
            config = AutoConfig.from_pretrained(
                model_path, trust_remote_code=trust_remote_code)
        except Exception as e:
            message = (
                f'Load model config with transformers=={trans_version}'
                ' failed. '
                'Please make sure model can be loaded with transformers API.')
            _handle_exception(e, 'transformers', logger, message=message)
        return config

    def __check_model_transformers_version(config, trans_version):
        """check model transformers version."""
        logger.debug('Checking <Model> required transformers version.')
        try:
            model_trans_version = getattr(config, 'transformers_version', None)
            if model_trans_version is not None:
                model_trans_version = version.parse(model_trans_version)
                assert trans_version >= model_trans_version, \
                    'Version mismatch.'
        except Exception as e:
            message = (f'model `{model_path}` requires '
                       f'transformers version {model_trans_version} '
                       f'but transformers {trans_version} is installed.')
            _handle_exception(e, 'transformers', logger, message=message)

    def __check_model_dtype_support(config, device_type):
        """Checking model dtype support."""
        logger.debug('Checking <Model> dtype support.')

        import torch

        from lmdeploy.pytorch.config import ModelConfig
        from lmdeploy.utils import is_bf16_supported

        try:
            model_config = ModelConfig.from_hf_config(config,
                                                      model_path=model_path,
                                                      dtype=dtype)
            if model_config.dtype == torch.bfloat16:
                assert is_bf16_supported(device_type), (
                    'bf16 is not supported on your device')
        except AssertionError as e:
            message = (
                f'Your device does not support `{model_config.dtype}`. '
                'You can set `dtype` to float16 in PyTorchEngineConfig or '
                '`--dtype float16` to api_server.\n'
                'Note that this might have negative effect!')
            _handle_exception(e, 'Model', logger, message=message)
        except Exception as e:
            message = (f'Checking failed with error {e}',
                       'Please send issue to LMDeploy with error logs.')
            _handle_exception(e, 'Model', logger, message=message)

        return model_config

    _, trans_version = __check_transformers_version()
    config = __check_config(trans_version)
    __check_model_transformers_version(config, trans_version)
    __check_model_dtype_support(config, device_type)
    check_awq(config, device_type)


def check_model(model_path: str,
                trust_remote_code: bool = True,
                dtype: str = 'auto',
                device_type: str = 'cuda'):
    """check model requirements."""
    logger = get_logger('lmdeploy')
    logger.info('Checking model.')
    check_transformers_version(model_path, trust_remote_code, dtype,
                               device_type)


def check_adapter(path: str):
    """check adapter."""
    logger = get_logger('lmdeploy')
    logger.debug(f'Checking <Adapter>: {path}.')

    try:
        from peft import PeftConfig
        PeftConfig.from_pretrained(path)
    except Exception as e:
        message = ('Please make sure the adapter can be loaded with '
                   '`peft.PeftConfig.from_pretrained`\n')
        err_msg = '' if len(e.args) == 0 else e.args[0]
        if 'got an unexpected keyword argument' in err_msg:
            message += ('Or try remove all unexpected keywords '
                        'in `adapter_config.json`.')
        _handle_exception(e, 'Model', logger, message=message)


def check_adapters(adapter_paths: List[str]):
    """check adapters."""
    if len(adapter_paths) <= 0:
        return
    logger = get_logger('lmdeploy')
    logger.info('Checking adapters.')
    for path in adapter_paths:
        check_adapter(path)
